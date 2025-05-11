import { useState, useEffect } from 'react'
import DailyPlanChart from './components/DailyPlanChart'
import VesselSchedule from './components/VesselSchedule'
import DataEditor from './components/DataEditor'
import Chatbox from './components/Chatbox'
import axios from 'axios'
import logo from './assets/logo_oasis2.png'

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
    try {
      // Call the schedule optimizer API endpoint
      const response = await axios.post('/api/optimizer/schedule', {
        days: 30
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
        days: 30,  // Default to 30 days
        save_output: true,  // Save results to output files
      });
      
      if (response.data.success) {
        // Update schedule data with the returned schedule
        setData(prev => ({
          ...prev,
          schedule: response.data.schedule
        }));
        
        setOptimizationMessage({ 
          type: 'success', 
          text: 'Scheduler ran successfully! Schedule has been updated.' 
        });
        
        // Switch to view mode to show the results
        setAppMode('view');
        setVisualizationView('dailyPlan');
      } else {
        throw new Error(response.data.error || 'Unknown error');
      }
    } catch (error) {
      console.error('Failed to run scheduler:', error);
      setOptimizationMessage({ 
        type: 'error', 
        text: `Failed to run scheduler: ${error.message || 'Unknown error'}` 
      });
    } finally {
      setIsOptimizing(false);
      setIsRunningScheduler(false);
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen bg-gradient-to-br from-slate-50 to-slate-100">
      {/* Enhanced header with gradient */}
      <div className="bg-gradient-to-r from-white to-emerald-500 text-white p-5 shadow-lg">
        <div className="container mx-auto flex justify-between items-center">
          <div className="flex items-center gap-2">
            <div className="-ml-1">
              <img 
                src={logo} 
                alt="OASIS Logo" 
                className="h-18 w-auto" 
              />
            </div>
            <div>
              <h3 className="text-gray-700 font-light">Refinery Scheduling & Optimization</h3>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {/* Optimization buttons */}
            <button
              onClick={handleOptimizeVessels}
              className="px-3 py-1.5 !bg-emerald-900 rounded-md text-sm font-medium text-white border border-emerald-600/50 hover:!bg-emerald-700 transition-colors flex items-center gap-1.5"
              disabled={isOptimizing}
            >
              {isOptimizingVessels ? (
                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-solid border-white border-r-transparent"></span>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 13.5V3.75m0 9.75a1.5 1.5 0 010 3m0-3a1.5 1.5 0 000 3m0 3.75V16.5m12-3V3.75m0 9.75a1.5 1.5 0 010 3m0-3a1.5 1.5 0 000 3m0 3.75V16.5m-6-9V3.75m0 3.75a1.5 1.5 0 010 3m0-3a1.5 1.5 0 000 3m0 9.75V10.5" />
                </svg>
              )}
              Optimize Vessels
            </button>
            <button
              onClick={handleOptimizeSchedule}
              className="px-4 py-2 !bg-emerald-900 rounded-md text-sm font-medium text-blue-100 border border-blue-600/50 hover:!bg-emerald-700 transition-colors flex items-center gap-1.5"
              disabled={isOptimizing}
            >
              {isOptimizingSchedule ? (
                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-solid border-white border-r-transparent"></span>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 3v11.25A2.25 2.25 0 006 16.5h2.25M3.75 3h-1.5m1.5 0h16.5m0 0h1.5m-1.5 0v11.25A2.25 2.25 0 0118 16.5h-2.25m-7.5 0h7.5m-7.5 0l-1 3m8.5-3l1 3m0 0l.5 1.5m-.5-1.5h-9.5m0 0l-.5 1.5" />
                </svg>
              )}
              Optimize Schedule
            </button>
            <button
              onClick={handleRunScheduler}
              className="px-4 py-2 !bg-amber-600 rounded-md text-sm font-medium text-white border border-amber-600/50 hover:!bg-amber-700 transition-colors flex items-center gap-1.5"
              disabled={isOptimizing}
            >
              {isRunningScheduler ? (
                <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-solid border-white border-r-transparent"></span>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5.25 5.653c0-.856.917-1.398 1.667-.986l11.54 6.347a1.125 1.125 0 0 1 0 1.972l-11.54 6.347a1.125 1.125 0 0 1-1.667-.986V5.653Z" />
                </svg>
              )}
              Run Scheduler
            </button>
          </div>
        </div>
      </div>

      {/* Add this after the header section to show optimization messages */}
      {optimizationMessage && (
        <div className={`p-3 mb-4 rounded-lg text-sm font-medium ${
          optimizationMessage.type === 'success' 
            ? 'bg-green-100 text-green-800 border border-green-200' 
            : 'bg-red-100 text-red-800 border border-red-200'
        }`}>
          <div className="flex items-center">
            {optimizationMessage.type === 'success' ? (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            )}
            {optimizationMessage.text}
            <button 
              className="ml-auto text-slate-500 hover:text-slate-700"
              onClick={() => setOptimizationMessage(null)}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Main content area with chat on right */}
      <div className="flex-grow flex">
        {/* Left main content - 75% width */}
        <div className="w-3/4 p-5 overflow-y-auto flex flex-col">
          {/* View/Edit tabs with enhanced styling */}
          <div className="flex gap-3 mb-6">
            <button 
              onClick={() => setAppMode('view')}
              className={`px-5 py-2.5 rounded-lg font-medium text-sm transition-all duration-200 ${
                appMode === 'view' 
                  ? 'bg-gradient-to-r from-emerald-600 to-emerald-500 text-white shadow-md shadow-blue-500/20 ring-1 ring-blue-500/50' 
                  : 'bg-white text-blue-950 hover:bg-blue-50 shadow-sm'
              }`}
            >
              <div className="flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                View Data
              </div>
            </button>
            <button 
              onClick={() => setAppMode('edit')}
              className={`px-5 py-2.5 rounded-lg font-medium text-sm transition-all duration-200 ${
                appMode === 'edit' 
                  ? 'bg-gradient-to-r from-emerald-600 to-emerald-500 text-white shadow-md shadow-blue-500/20 ring-1 ring-blue-500/50' 
                  : 'bg-white text-blue-950 hover:bg-blue-50 shadow-sm'
              }`}
            >
              <div className="flex items-center gap-2">
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-5 h-5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
                </svg>
                Edit Data
              </div>
            </button>
          </div>

          {/* VIEW MODE: Visualization selector tabs */}
          {appMode === 'view' && (
            <div className="flex gap-2 mb-5 bg-slate-100 p-1 rounded-lg w-fit">
              <button 
                onClick={() => setVisualizationView('dailyPlan')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                  visualizationView === 'dailyPlan' 
                    ? 'bg-white text-blue-700 shadow-sm' 
                    : 'text-slate-600 hover:text-slate-800'
                }`}
              >
                Daily Plan
              </button>
              <button 
                onClick={() => setVisualizationView('vessels')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all duration-200 ${
                  visualizationView === 'vessels' 
                    ? 'bg-white text-blue-700 shadow-sm' 
                    : 'text-slate-600 hover:text-slate-800'
                }`}
              >
                Vessel Schedule
              </button>
            </div>
          )}

          {/* EDIT MODE: Data type selector tabs */}
          {appMode === 'edit' && (
            <div className="flex flex-col gap-2 mb-5">
              <div className="flex gap-2 border-b border-slate-200">
                <button 
                  onClick={() => setEditorMode('input')}
                  className={`px-4 py-2 rounded-tl-lg rounded-tr-lg text-sm font-medium transition-all duration-200 ${
                    editorMode === 'input' 
                      ? 'bg-gray-400 text-emerald-700 border-t border-l border-r border-slate-200' 
                      : 'bg-slate-100 text-slate-300 hover:bg-slate-100/80 hover:text-slate-700'
                  }`}
                >
                  Input Data
                </button>
                <button 
                  onClick={() => setEditorMode('plant')}
                  className={`px-4 py-2 rounded-tl-lg rounded-tr-lg text-sm font-medium transition-all duration-200 ${
                    editorMode === 'plant' 
                      ? 'bg-gray-400 text-emerald-700 border-t border-l border-r border-slate-200' 
                      : 'bg-slate-100 text-slate-300 hover:bg-slate-100/80 hover:text-slate-700'
                  }`}
                >
                  Plant Data
                </button>
              </div>

              {/* Input data editor sub-tabs */}
              {editorMode === 'input' && (
                <div className="flex gap-2 px-2 py-2 flex-wrap">
                  <button 
                    onClick={() => setActiveEditor('tanks')}
                    className={`px-4 py-2 rounded-full text-xs font-medium transition-all duration-200 ${
                      activeEditor === 'tanks' 
                        ? '!bg-emerald-600 text-white shadow-sm' 
                        : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                    }`}
                  >
                    Tank Data
                  </button>
                  <button 
                    onClick={() => setActiveEditor('vessels')}
                    className={`px-4 py-2 rounded-full text-xs font-medium transition-all duration-200 ${
                      activeEditor === 'vessels' 
                        ? '!bg-emerald-600 text-white shadow-sm' 
                        : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                    }`}
                  >
                    Vessel Data
                  </button>
                  <button 
                    onClick={() => setActiveEditor('feedstock_parcels')}
                    className={`px-4 py-2 rounded-full text-xs font-medium transition-all duration-200 ${
                      activeEditor === 'feedstock_parcels' 
                        ? '!bg-emerald-600 text-white shadow-sm' 
                        : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                    }`}
                  >
                    Feedstock Parcels
                  </button>
                  <button 
                    onClick={() => setActiveEditor('feedstock_requirements')}
                    className={`px-4 py-2 rounded-full text-xs font-medium transition-all duration-200 ${
                      activeEditor === 'feedstock_requirements' 
                        ? '!bg-emerald-600 text-white shadow-sm' 
                        : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                    }`}
                  >
                    Feedstock Requirements
                  </button>
                </div>
              )}

              {/* Plant data editor sub-tabs */}
              {editorMode === 'plant' && (
                <div className="flex gap-2 px-2 py-2 flex-wrap">
                  <button 
                    onClick={() => setActiveEditor('plants')}
                    className={`px-4 py-2 rounded-full text-xs font-medium transition-all duration-200 ${
                      activeEditor === 'plants' 
                        ? '!bg-emerald-600 text-white shadow-sm' 
                        : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                    }`}
                  >
                    Plants
                  </button>
                  <button 
                    onClick={() => setActiveEditor('crudes')}
                    className={`px-4 py-2 rounded-full text-xs font-medium transition-all duration-200 ${
                      activeEditor === 'crudes' 
                        ? '!bg-emerald-600 text-white shadow-sm' 
                        : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                    }`}
                  >
                    Crude Types
                  </button>
                  <button 
                    onClick={() => setActiveEditor('recipes')}
                    className={`px-4 py-2 rounded-full text-xs font-medium transition-all duration-200 ${
                      activeEditor === 'recipes' 
                        ? '!bg-emerald-600 text-white shadow-sm' 
                        : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                    }`}
                  >
                    Recipes
                  </button>
                  <button 
                    onClick={() => setActiveEditor('routes')}
                    className={`px-4 py-2 rounded-full text-xs font-medium transition-all duration-200 ${
                      activeEditor === 'routes' 
                        ? '!bg-emerald-600 text-white shadow-sm' 
                        : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                    }`}
                  >
                    Routes
                  </button>
                  <button 
                    onClick={() => setActiveEditor('vessel_types')}
                    className={`px-4 py-2 rounded-full text-xs font-medium transition-all duration-200 ${
                      activeEditor === 'vessel_types' 
                        ? '!bg-emerald-600 text-white shadow-sm' 
                        : 'bg-blue-50 text-blue-700 hover:bg-blue-100'
                    }`}
                  >
                    Vessel Types
                  </button>
                </div>
              )}
            </div>
          )}

          {/* Main content area with enhanced card styling */}
          <div className="bg-white rounded-xl shadow-lg p-5 flex-grow border border-slate-100">
            {isLoading ? (
              <div className="flex items-center justify-center h-full">
                <div className="flex flex-col items-center">
                  <div className="inline-block h-12 w-12 animate-spin rounded-full border-4 border-solid border-blue-600 border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]"></div>
                  <p className="mt-4 text-slate-500 font-medium">Loading data...</p>
                </div>
              </div>
            ) : error ? (
              <div className="flex items-center justify-center h-full">
                <div className="text-red-500 text-center max-w-md bg-red-50 p-6 rounded-lg border border-red-100">
                  <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
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
                    {visualizationView === 'dailyPlan' && <DailyPlanChart schedule={data.schedule} />}
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
                      setData(prev => ({
                        ...prev,
                        [activeEditor]: updatedData
                      }))
                      
                      // Show success message
                      setOptimizationMessage({ 
                        type: 'success', 
                        text: `${activeEditor.charAt(0).toUpperCase() + activeEditor.slice(1).replace('_', ' ')} data updated successfully!` 
                      })
                      
                      // Save to backend
                      axios.post('/api/save-data', {
                        type: activeEditor,
                        content: updatedData
                      })
                        .then(response => console.log(`Saved ${activeEditor} data to server`))
                        .catch(error => {
                          console.error(`Error saving ${activeEditor} data to server`, error)
                          setOptimizationMessage({ 
                            type: 'error', 
                            text: `Failed to save ${activeEditor} data to server.` 
                          })
                        })
                    }}
                  />
                )}
              </>
            )}
          </div>
        </div>
        
        {/* Right sidebar - Chat - 25% width with enhanced styling */}
        <div className="w-1/4 border-l border-slate-200 bg-white">
          <div className="bg-gradient-to-r from-slate-100 to-slate-50 border-b border-slate-200 p-3">
            <div className="flex justify-between items-center">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 !bg-emerald-600 rounded-full"></div>
                <h3 className="text-sm font-medium text-slate-700">OASIS Assistant</h3>
              </div>
              <button 
                onClick={() => setShowChat(!showChat)}
                className="p-1.5 rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-colors"
              >
                {showChat ? (
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 5.25l-7.5 7.5-7.5-7.5m15 6l-7.5 7.5-7.5-7.5" />
                  </svg>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l7.5-7.5 7.5 7.5m-15 6l7.5-7.5 7.5 7.5" />
                  </svg>
                )}
              </button>
            </div>
          </div>
          
          {showChat && (
            <div className="h-full">
              <Chatbox schedule={data.schedule} tanks={data.tanks} vessels={data.vessels} />
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default App
