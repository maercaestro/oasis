import { useState, useEffect } from 'react'
import DailyPlanChart from './components/DailyPlanChart'
import VesselSchedule from './components/VesselSchedule'
import DataEditor from './components/DataEditor'
import Chatbox from './components/Chatbox'
import axios from 'axios'
import logo from '/oasis-new.png'
import ScheduleDashboard from './components/ScheduleDashboard';

function App() {
  const [appMode, setAppMode] = useState('view')
  const [visualizationView, setVisualizationView] = useState('dailyPlan')
  const [editorMode, setEditorMode] = useState('input')
  const [activeEditor, setActiveEditor] = useState('tanks')
  const [showChat, setShowChat] = useState(true)
  const [isOptimizing, setIsOptimizing] = useState(false)
  const [isOptimizingVessels, setIsOptimizingVessels] = useState(false)
  const [isOptimizingSchedule, setIsOptimizingSchedule] = useState(false)
  const [optimizationMessage, setOptimizationMessage] = useState(null)
  const [isRunningScheduler, setIsRunningScheduler] = useState(false);
  
  const [data, setData] = useState({
    schedule: [],
    tanks: {},
    vessels: [],
    crudes: {},
    recipes: {},
    plants: {}, // Add plants
    routes: [],  // Add routes
    vessel_types: [], // Add vessel types
    feedstock_parcels: [],
    feedstock_requirements: []
  })
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [originalSchedule, setOriginalSchedule] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setIsLoading(true)
        const response = await axios.get('/api/data')
        
        // Initialize with all data types, including dynamic data
        setData({
          schedule: response.data.schedule || [],
          tanks: response.data.tanks || {},
          vessels: response.data.vessels || [],
          crudes: response.data.crudes || {},
          recipes: response.data.recipes || {},
          plants: response.data.plants || {},  // Fix potential name mismatch
          routes: response.data.routes || {},
          vessel_types: response.data.vessel_types || [],
          feedstock_parcels: response.data.feedstock_parcels || [],
          feedstock_requirements: response.data.feedstock_requirements || []
        })
        
        setIsLoading(false)
      } catch (err) {
        setError('Failed to fetch data from API. Is the backend server running?')
        console.error(err)
        setIsLoading(false)
      }
    }

    fetchData()
  }, [])

  const handleOptimizeVessels = async () => {
    setIsOptimizing(true);
    setIsOptimizingVessels(true);
    try {
      // Call the vessel optimizer API endpoint with use_file_requirements set to true
      const response = await axios.post('/api/vessel-optimizer/optimize', {
        horizon_days: 30,
        use_file_requirements: true  // This will make it use feedstock_requirements.json
      });
      
      if (response.data.success) {
        // Update vessels data with optimized results
        setData(prev => ({
          ...prev,
          vessels: response.data.vessels
        }));
        
        setOptimizationMessage({ 
          type: 'success', 
          text: 'Vessels optimized successfully!' 
        });
      } else {
        throw new Error(response.data.error || 'Unknown error');
      }
    } catch (error) {
      console.error('Failed to optimize vessels:', error);
      setOptimizationMessage({ 
        type: 'error', 
        text: `Failed to optimize vessels: ${error.message || 'Unknown error'}` 
      });
    } finally {
      setIsOptimizing(false);
      setIsOptimizingVessels(false);
    }
  };

  const handleOptimizeSchedule = async () => {
    setIsOptimizing(true);
    setIsOptimizingSchedule(true);
    // Store the original schedule for comparison
    setOriginalSchedule(data.schedule);
    
    try {
      // Fix #1: Use correct URL
      // Fix #2: Send the current schedule data
      const response = await axios.post('/api/optimizer/optimize', {
        days: 30,
        schedule: data.schedule,  // Add the current schedule
        objective: 'margin'       // You can also specify the objective
      });
      
      if (response.data.success) {
        // Update schedule data with optimized results
        setData(prev => ({
          ...prev,
          schedule: response.data.schedule
        }));
        
        setOptimizationMessage({ 
          type: 'success', 
          text: 'Schedule optimized successfully!' 
        });
        
        // Switch to view mode to show the optimized schedule
        setAppMode('view');
        setVisualizationView('dailyPlan');
      } else {
        throw new Error(response.data.error || 'Unknown error');
      }
    } catch (error) {
      console.error('Failed to optimize schedule:', error);
      setOptimizationMessage({ 
        type: 'error', 
        text: `Failed to optimize schedule: ${error.message || 'Unknown error'}` 
      });
      setOriginalSchedule(null); // Clear original schedule if optimization failed
    } finally {
      setIsOptimizing(false);
      setIsOptimizingSchedule(false);
    }
  };

  const handleRunScheduler = async () => {
    setIsOptimizing(true);
    setIsRunningScheduler(true);
    try {
      // Call the scheduler API endpoint
      const response = await axios.post('/api/scheduler/run', {
        days: 30,
        save_output: true,
      });
      
      if (response.data.success) {
        // CURRENT CODE - just updates schedule
        setData(prev => ({
          ...prev,
          schedule: response.data.daily_plans || response.data.schedule
        }));
        
        // ADD THIS: Refresh all data to get latest tank states
        const refreshResponse = await axios.get('/api/data');
        setData(prev => ({
          ...prev,
          tanks: refreshResponse.data.tanks || prev.tanks,
          vessels: refreshResponse.data.vessels || prev.vessels,
          // Other data you want to refresh
        }));
        
        setOptimizationMessage({ 
          type: 'success', 
          text: 'Scheduler ran successfully! Schedule and inventory updated.' 
        });
        
        // Rest of the function...
      }
    } catch (error) {
      // Error handling...
    } finally {
      setIsOptimizing(false);
      setIsRunningScheduler(false);
    }
  };

  // Add this function in your App component
  const refreshData = async () => {
    try {
      setIsLoading(true);
      const response = await axios.get('/api/data?nocache=' + Date.now()); // Add cache-busting parameter
      
      setData({
        schedule: response.data.schedule || [],
        tanks: response.data.tanks || {},
        vessels: response.data.vessels || [],
        // ...other data
      });
      
      setIsLoading(false);
    } catch (err) {
      console.error("Error refreshing data:", err);
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-gradient-to-br from-[#112D32] via-[#254E58] to-[#4F4A41] text-white">
      {/* Enhanced header with teal-brown theme */}
      <div className="bg-gradient-to-r from-[#112D32] via-[#254E58] to-[#4F4A41] text-white p-6 shadow-2xl sticky top-0 z-50 border-b border-[#88BDBC]/30">
        <div className="container mx-auto flex justify-between items-center">
          <div className="flex items-center gap-4">
            {/* Enhanced logo container with teal glassmorphic effect */}
            <div className="relative group">
              <div className="absolute inset-0 !bg-gradient-to-r from-[#88BDBC] to-[#254E58] rounded-xl blur-lg opacity-60 group-hover:opacity-80 transition-opacity duration-300"></div>
              <div className="relative bg-white/10 backdrop-blur-md rounded-xl p-3 border border-[#88BDBC]/20 shadow-lg">
                <img 
                  src={logo} 
                  alt="OASIS Logo" 
                  className="h-6 w-auto drop-shadow-lg group-hover:scale-105 transition-transform duration-300" 
                />
              </div>
            </div>
            {/* Enhanced typography with teal gradient */}
            <div className="ml-2">
              <h3 className="text-sm font-medium !text-white tracking-wider">
                Refinery Scheduling & Optimization
              </h3>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {/* Enhanced optimization buttons with teal-brown glassmorphic design */}
            <button
              onClick={handleOptimizeVessels}
              className="px-4 py-2.5 !bg-[#254E58] backdrop-blur-md border !border-[#88bdbc] rounded-lg text-sm font-semibold !text-white shadow-lg hover:!bg-[#88BDBC] hover:!border-[#254E58] transition-all duration-200 ease-in-out flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-[#88BDBC]/50 disabled:opacity-50 disabled:cursor-not-allowed group"
              disabled={isOptimizing}
            >
              {isOptimizingVessels ? (
                <div className="dual-ring-small"></div>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4 group-hover:scale-110 transition-transform">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 13.5V3.75m0 9.75a1.5 1.5 0 010 3m0-3a1.5 1.5 0 000 3m0 3.75V16.5m12-3V3.75m0 9.75a1.5 1.5 0 010 3m0-3a1.5 1.5 0 000 3m0 3.75V16.5m-6-9V3.75m0 3.75a1.5 1.5 0 010 3m0-3a1.5 1.5 0 000 3m0 9.75V10.5" />
                </svg>
              )}
              Optimize Vessels
            </button>
            <button
              onClick={handleOptimizeSchedule}
              className="px-4 py-2.5 !bg-[#254E58] backdrop-blur-md border !border-[#88bdbc] rounded-lg text-sm font-semibold !text-white shadow-lg hover:!bg-[#88BDBC] hover:!border-[#254E58] transition-all duration-200 ease-in-out flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-[#88BDBC]/50 disabled:opacity-50 disabled:cursor-not-allowed group"
              disabled={isOptimizing}
            >
              {isOptimizingSchedule ? (
                <div className="dual-ring-small"></div>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4 group-hover:scale-110 transition-transform">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5" />
                </svg>
              )}
              Optimize Schedule
            </button>
            <button
              onClick={handleRunScheduler}
              className="px-4 py-2.5 !bg-[#254E58] backdrop-blur-md border !border-[#88bdbc] rounded-lg text-sm font-semibold !text-white shadow-lg hover:!bg-[#88BDBC] hover:!border-[#254E58] transition-all duration-200 ease-in-out flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-[#88BDBC]/50 disabled:opacity-50 disabled:cursor-not-allowed group"
              disabled={isOptimizing}
            >
              {isRunningScheduler ? (
                <div className="dual-ring-small"></div>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4 group-hover:scale-110 transition-transform">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653Z" />
                </svg>
              )}
              Run Scheduler
            </button>
          </div>
        </div>
      </div>

      {/* Enhanced notification messages with teal-brown theme */}
      {optimizationMessage && (
        <div className={`p-4 m-4 rounded-lg text-sm font-medium shadow-lg border backdrop-blur-md ${ 
          optimizationMessage.type === 'success' 
            ? 'bg-[#88BDBC]/20 text-[#88BDBC] border-[#88BDBC]/30' 
            : 'bg-red-500/20 text-red-200 border-red-400/30'
        }`}>
          <div className="flex items-center">
            {optimizationMessage.type === 'success' ? (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-3 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            )}
            <span className="flex-grow">{optimizationMessage.text}</span>
            <button 
              className={`ml-auto ${optimizationMessage.type === 'success' ? 'text-[#88BDBC] hover:text-white' : 'text-red-300 hover:text-red-100'} p-1 rounded-full hover:bg-white/10 transition-colors`}
              onClick={() => setOptimizationMessage(null)}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Main content area with chat on right - enhanced dark theme */}
      <div className="flex-grow flex overflow-hidden">
        {/* Left main content - 70% width with teal glassmorphic styling */}
        <div className="w-7/10 p-6 overflow-y-auto flex flex-col space-y-6" style={{width: '70%'}}>
          {/* View/Edit tabs with teal-brown theme */}
          <div className="flex gap-4">
            <button 
              onClick={() => setAppMode('view')}
              className={`px-6 py-3 rounded-lg font-semibold text-sm transition-all duration-200 ease-in-out flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-offset-2 backdrop-blur-md border ${ 
                appMode === 'view' 
                  ? '!bg-gradient-to-r !from-[#88BDBC] !to-[#254E58] !text-gray-50 shadow-lg !border-[#88BDBC] focus:!ring-[#88BDBC]' 
                  : '!bg-white/10 !text-[#88BDBC] hover:!bg-[#88BDBC]/20 !border-white/20 hover:!border-[#88BDBC]/30 focus:!ring-[#88BDBC]/30'
              }`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              View Data
            </button>
            <button 
              onClick={() => setAppMode('edit')}
              className={`px-6 py-3 rounded-lg font-semibold text-sm transition-all duration-200 ease-in-out flex items-center gap-2 focus:outline-none focus:ring-2 focus:ring-offset-2 backdrop-blur-md border ${ 
                appMode === 'edit' 
                  ? '!bg-gradient-to-r !from-[#88BDBC] !to-[#254E58] !text-gray-50 shadow-lg !border-[#88BDBC] focus:!ring-[#88BDBC]' 
                  : '!bg-white/10 !text-[#88BDBC] hover:!bg-white/20 !border-white/20 hover:!border-white/30 focus:!ring-white/30'
              }`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
              </svg>
              Edit Data
            </button>
          </div>

          {/* VIEW MODE: Visualization selector tabs with teal-brown theme */}
          {appMode === 'view' && (
            <div className="bg-white/10 backdrop-blur-md p-2 rounded-lg flex gap-2 w-fit shadow-lg border border-[#88BDBC]/20">
              <button 
                onClick={() => setVisualizationView('dailyPlan')}
                className={`px-5 py-2 rounded-md text-sm font-medium transition-all duration-200 ease-in-out ${ 
                  visualizationView === 'dailyPlan' 
                    ? '!bg-[#88BDBC] !text-white shadow-md backdrop-blur-sm border !border-[#88BDBC]' 
                    : '!text-[#254e58] hover:!bg-[#254E58] hover:!text-white'
                }`}
              >
                Daily Plan
              </button>
              <button 
                onClick={() => setVisualizationView('vessels')}
                className={`px-5 py-2 rounded-md text-sm font-medium transition-all duration-200 ease-in-out ${ 
                  visualizationView === 'vessels' 
                    ? '!bg-[#88BDBC] !text-white shadow-md backdrop-blur-sm border !border-[#88BDBC]' 
                    : '!text-[#254e58] hover:!bg-[#254E58] hover:!text-white'
                }`}
              >
                Vessel Schedule
              </button>
            </div>
          )}

          {/* EDIT MODE: Data type radio buttons with teal-brown theme */}
          {appMode === 'edit' && (
            <div className="flex flex-col gap-0">
              <div className="flex justify-between items-center pb-3">
                <h3 className="text-lg font-semibold text-[#88BDBC]">Data Editor</h3>
                
                {/* Radio buttons for Input/Plant data */}
                <div className="flex items-center gap-6 bg-[#254E58]/20 backdrop-blur-sm p-2 rounded-lg border border-[#88BDBC]/20">
                  <label className="flex items-center gap-2 cursor-pointer group">
                    <input
                      type="radio"
                      name="editorMode"
                      value="input"
                      checked={editorMode === 'input'}
                      onChange={() => setEditorMode('input')}
                      className="sr-only"
                    />
                    <div className={`w-4 h-4 rounded-full border-2 transition-all duration-200 flex items-center justify-center ${
                      editorMode === 'input' 
                        ? 'border-[#88BDBC] bg-gradient-to-r from-[#88BDBC] to-[#254E58]' 
                        : 'border-white/50 bg-transparent group-hover:border-[#88BDBC]/50'
                    }`}>
                      {editorMode === 'input' && (
                        <div className="w-2 h-2 rounded-full bg-white"></div>
                      )}
                    </div>
                    <span className={`text-sm font-medium transition-colors ${
                      editorMode === 'input' ? 'text-[#88BDBC]' : 'text-white group-hover:text-[#88BDBC]'
                    }`}>
                      Input Data
                    </span>
                  </label>
                  
                  <label className="flex items-center gap-2 cursor-pointer group">
                    <input
                      type="radio"
                      name="editorMode"
                      value="plant"
                      checked={editorMode === 'plant'}
                      onChange={() => setEditorMode('plant')}
                      className="sr-only"
                    />
                    <div className={`w-4 h-4 rounded-full border-2 transition-all duration-200 flex items-center justify-center ${
                      editorMode === 'plant' 
                        ? 'border-[#88BDBC] bg-gradient-to-r from-[#88BDBC] to-[#254E58]' 
                        : 'border-white/50 bg-transparent group-hover:border-[#88BDBC]/50'
                    }`}>
                      {editorMode === 'plant' && (
                        <div className="w-2 h-2 rounded-full bg-white"></div>
                      )}
                    </div>
                    <span className={`text-sm font-medium transition-colors ${
                      editorMode === 'plant' ? 'text-[#88BDBC]' : 'text-white group-hover:text-[#88BDBC]'
                    }`}>
                      Plant Data
                    </span>
                  </label>
                </div>
              </div>

              {/* Sub-tabs container with teal-brown theme */}
              <div className="bg-white/10 backdrop-blur-md p-2 rounded-lg flex gap-2 w-fit shadow-lg border border-[#88BDBC]/20">
                {/* Input data editor sub-tabs */}
                {editorMode === 'input' && (
                  <div className="flex gap-2 flex-wrap">
                    {['tanks', 'vessels', 'feedstock_parcels', 'feedstock_requirements'].map(editor => (
                      <button 
                        key={editor}
                        onClick={() => setActiveEditor(editor)}
                        className={`px-4 py-2 rounded-full text-xs font-semibold transition-all duration-200 ease-in-out shadow-sm hover:shadow-md focus:outline-none focus:ring-2 focus:ring-offset-1 ${ 
                          activeEditor === editor 
                            ? '!bg-[#88BDBC] !text-white shadow-md backdrop-blur-sm border !border-[#88BDBC]' 
                            : '!text-[#254e58] hover:!bg-[#254E58] hover:!text-white'
                        }`}
                      >
                        {editor.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </button>
                    ))}
                  </div>
                )}

                {/* Plant data editor sub-tabs */}
                {editorMode === 'plant' && (
                  <div className="flex gap-2 flex-wrap">
                    {['plants', 'crudes', 'recipes', 'routes', 'vessel_types'].map(editor => (
                      <button 
                        key={editor}
                        onClick={() => setActiveEditor(editor)}
                        className={`px-4 py-2 rounded-full text-xs font-semibold transition-all duration-200 ease-in-out shadow-sm hover:shadow-md focus:outline-none focus:ring-2 focus:ring-offset-1 ${ 
                          activeEditor === editor 
                            ? '!bg-[#88BDBC] !text-white shadow-md backdrop-blur-sm border !border-[#88BDBC]' 
                            : '!text-[#254e58] hover:!bg-[#254E58] hover:!text-white'
                        }`}
                      >
                        {editor.replace('_', ' ').replace(/\b\w/g, l => l.toUpperCase())}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Main content area with enhanced glassmorphic styling */}
          <div className="bg-white/10 backdrop-blur-md rounded-xl shadow-2xl p-6 flex-grow border border-white/20">
            {isLoading ? (
              <div className="flex items-center justify-center h-full">
                <div className="flex flex-col items-center">
                  <div className="dual-ring-large"></div>
                  <p className="mt-5 text-[#88BDBC] font-semibold text-lg">Loading data...</p>
                </div>
              </div>
            ) : error ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-red-300 text-center max-w-md bg-red-500/20 backdrop-blur-md p-6 rounded-lg border border-red-400/30">
                  <div className="w-16 h-16 bg-red-500/30 rounded-full flex items-center justify-center mx-auto mb-4">
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" className="w-8 h-8">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z" />
                    </svg>
                  </div>
                  <p className="text-lg font-medium mb-2">Connection Error</p>
                  <p>{error}</p>
                </div>
              </div>
            ) : (
              <>
                {/* VIEW MODE: Show visualizations */}
                {appMode === 'view' && (
                  <>
                    {visualizationView === 'dailyPlan' && (
                      <DailyPlanChart 
                        schedule={data.schedule} 
                        originalSchedule={originalSchedule} // Pass original schedule for comparison
                      />
                    )}
                    {visualizationView === 'vessels' && (
                      <VesselSchedule 
                        vessels={data.vessels} 
                        onVesselUpdate={(vesselId, updatedVessel) => {
                          // Update local state
                          setData(prev => {
                            // Make a deep copy of vessels to avoid reference issues
                            const newVessels = {...prev.vessels}
                            // Update the specific vessel
                            newVessels[vesselId] = updatedVessel
                            return {
                              ...prev,
                              vessels: newVessels
                            }
                          })
                          
                          // Show success message
                          setOptimizationMessage({ 
                            type: 'success', 
                            text: `Vessel ${updatedVessel.vessel_id} schedule updated successfully!` 
                          })
                          
                          // Save to backend
                          axios.post('/api/save-data', {
                            type: 'vessels',
                            content: updatedVessel
                          })
                            .then(response => console.log('Saved to server'))
                            .catch(error => console.error('Error saving to server', error))
                        }}
                      />
                    )}
                  </>
                )}
                
                {/* EDIT MODE: Show data editors */}
                {appMode === 'edit' && (
                  <DataEditor 
                    dataType={activeEditor} 
                    data={
                      activeEditor === 'recipes' 
                        ? { ...data[activeEditor], crudes: data.crudes }  // Pass crudes data for recipe editor
                        : data[activeEditor]
                    }
                    onSave={(updatedData) => {
                      // Save to backend first
                      axios.post('/api/save-data', {
                        type: activeEditor,
                        content: updatedData
                      })
                      .then(() => {
                        // Then refresh all data
                        refreshData();
                        
                        // Show success message
                        setOptimizationMessage({ 
                          type: 'success', 
                          text: `${activeEditor.charAt(0).toUpperCase() + activeEditor.slice(1).replace('_', ' ')} data updated successfully!` 
                        });
                      })
                      .catch(error => {
                        console.error(`Error saving ${activeEditor} data`, error);
                        setOptimizationMessage({ 
                          type: 'error', 
                          text: `Failed to save ${activeEditor} data.` 
                        });
                      });
                    }}
                  />
                )}
              </>
            )}
          </div>
        </div>
        
        {/* Right sidebar - Dashboard and Chat - 30% width with teal-brown theme */}
        <div className="w-3/10 p-4 border-l border-[#88BDBC]/30 flex flex-col bg-[#254E58]/20 backdrop-blur-sm" style={{width: '30%'}}> {/* Teal-brown bg for chat sidebar */}
    
          {/* Chat section - remaining space */}
          <div className="flex-grow flex flex-col min-h-0">
            <div className="flex items-center justify-between mb-3 flex-shrink-0">
              <h3 className="text-xl font-semibold text-[#88BDBC]">Assistant</h3>
              <button 
                onClick={() => setShowChat(!showChat)}
                className="text-[#254E58] hover:text-gray-700 text-sm flex items-center p-1 rounded-md hover:bg-[#88BDBC]/20 transition-colors"
              >
                {showChat ? (
                  <>
                    <span className="font-medium">Hide</span>
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 ml-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                  </>
                ) : (
                  <>
                    <span className="font-medium">Show</span>
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4 ml-1.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 15l7-7 7 7" />
                    </svg>
                  </>
                )}
              </button>
            </div>
            
            {showChat && (
              <div className="flex-1 min-h-0">
                <Chatbox />
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

export default App;
