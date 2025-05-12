import { useState, useEffect } from 'react'
import axios from 'axios'

function DataEditor({ dataType, data, onSave }) {
  // Initial setup with proper defensive handling
  const initialData = data || (dataType === 'tanks' || dataType === 'plants' || dataType === 'crudes' || dataType === 'recipes' ? {} : []);
  const [editableData, setEditableData] = useState(initialData);
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [successMessage, setSuccessMessage] = useState(null)
  const [activeTab, setActiveTab] = useState(dataType || 'tanks')
  
  useEffect(() => {
    // Make sure we set default values if data is undefined
    setEditableData(data || (dataType === 'tanks' || dataType === 'plants' || dataType === 'crudes' || dataType === 'recipes' ? {} : []))
    setError(null)
    setSuccessMessage(null)
    setActiveTab(dataType || 'tanks')
  }, [data, dataType])
  
  const handleSaveData = async () => {
    try {
      setIsSubmitting(true)
      setError(null)
      
      // Prepare data for saving
      let dataToSave = editableData;
      
      // If we're dealing with vessels that might need conversion
      if (dataType === 'vessels' && !Array.isArray(data) && Array.isArray(editableData)) {
        // Convert array back to object if the original data was an object
        dataToSave = editableData.reduce((obj, vessel) => {
          obj[vessel.vessel_id] = vessel;
          return obj;
        }, {});
      }
      
      // Save changes via correct API endpoint
      await axios.post('/api/save-data', {  // Changed from '/api/data' to '/api/save-data'
        type: dataType,
        content: dataToSave
      })
      
      onSave(dataToSave)
      setSuccessMessage(`${dataType} data updated successfully.`)
      
      // Clear success message after 3 seconds
      setTimeout(() => {
        setSuccessMessage(null)
      }, 3000)
      
      setIsSubmitting(false)
    } catch (err) {
      setError(`Failed to save changes: ${err.message || 'Unknown error'}`)
      setIsSubmitting(false)
    }
  }
  
  if (!data) {
    return <p className="text-slate-500">No data available to edit.</p>
  }
  
  // Render editor based on selected tab/dataType
  const renderEditor = () => {
    switch (dataType) {
      case 'tanks':
        return <TankDataEditor 
          tanks={editableData} 
          setTanks={setEditableData} 
          crudes={data.crudes} // Pass crudes data here
        />;
      case 'vessels':
        return <VesselDataEditor vessels={editableData} setVessels={setEditableData} />;
      case 'plants':
        return <PlantDataEditor plants={editableData} setPlants={setEditableData} />;
      case 'crudes':
        return <CrudeDataEditor crudes={editableData} setCrudes={setEditableData} />;
      case 'recipes':
        return <RecipeDataEditor recipes={editableData} setRecipes={setEditableData} crudes={data.crudes} />;
      case 'routes':
        return <RouteDataEditor routes={editableData} setRoutes={setEditableData} />;
      case 'vessel_types':
        return <VesselTypeDataEditor vesselTypes={editableData} setVesselTypes={setEditableData} />;
      case 'feedstock_parcels':
        return <FeedstockParcelEditor parcels={editableData} setParcels={setEditableData} />;
      case 'feedstock_requirements':
        console.log("Rendering FeedstockRequirementEditor with crudes:", data.crudes);
        return <FeedstockRequirementEditor 
          requirements={editableData} 
          setRequirements={setEditableData} 
          crudes={data.crudes}  // Pass crudes data here
        />;
      default:
        return null;
    }
  };

  return (
    <div>
      {/* Render the appropriate editor */}
      {renderEditor()}

      {/* Action buttons and status */}
      <div className="mt-4 flex items-center">
        <button
          onClick={handleSaveData}
          disabled={isSubmitting}
          className="px-4 py-2 !bg-emerald-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:bg-blue-300 disabled:cursor-not-allowed transition"
        >
          {isSubmitting ? 'Saving...' : 'Save Changes'}
        </button>

        {successMessage && (
          <span className="ml-3 text-green-600 text-sm">{successMessage}</span>
        )}

        {error && (
          <span className="ml-3 text-red-600 text-sm">{error}</span>
        )}
      </div>
    </div>
  );
}

// Tank Editor Component
function TankDataEditor({ tanks, setTanks, crudes }) {
    const tanksData = tanks || {};
  // Force load crude data if not provided
  const [loadedCrudes, setLoadedCrudes] = useState(crudes || {});
  const [isLoading, setIsLoading] = useState(!crudes);
  const [isAddingTank, setIsAddingTank] = useState(false);
  const [newTankName, setNewTankName] = useState('');
  const [error, setError] = useState('');
  
  useEffect(() => {
    const fetchCrudes = async () => {
      try {
        setIsLoading(true);
        const response = await axios.get('/api/data');
        console.log("API response:", response.data);
        if (response.data && response.data.crudes) {
          setLoadedCrudes(response.data.crudes);
          console.log("Set loaded crudes:", response.data.crudes);
        }
      } catch (err) {
        console.error("Error loading crude data:", err);
        setError("Failed to load crude grades");
      } finally {
        setIsLoading(false);
      }
    };
    
    if (!crudes || Object.keys(crudes || {}).length === 0) {
      fetchCrudes();
    } else {
      // If crudes were passed as props, make sure we use them
      setLoadedCrudes(crudes);
    }
  }, [crudes]);
  
  // Use loaded crudes or passed crudes
  const crudesData = Object.keys(loadedCrudes).length > 0 ? loadedCrudes : (crudes || {});
  const allGrades = Object.keys(crudesData).filter(Boolean);
  
  console.log("Available Crude Grades:", allGrades);
  
  // Add this right after the dropdown where the options should appear
  useEffect(() => {
    // This will force a re-render when loadedCrudes changes
    console.log("Crude grades updated:", Object.keys(crudesData).length);
  }, [loadedCrudes]);
  
  // Handle empty tanks object
  if (Object.keys(tanksData).length === 0 && !isAddingTank) {
    return (
      <div className="text-center p-8">
        <p className="text-slate-500 mb-4">No tank data available to edit.</p>
        <button
          onClick={() => setIsAddingTank(true)}
          className="px-4 py-2 !bg-emerald-600 text-white rounded hover:bg-green-600"
        >
          + Add First Tank
        </button>
      </div>
    );
  }

  const handleTankPropertyChange = (tankName, property, value) => {
    setTanks(prev => ({
      ...prev,
      [tankName]: {
        ...prev[tankName],
        [property]: value
      }
    }))
  }
  
  // Add this function to delete a tank
  const deleteTank = (tankName) => {
    if (confirm(`Are you sure you want to delete tank "${tankName}"? This action cannot be undone.`)) {
      setTanks(prev => {
        const updatedTanks = {...prev};
        delete updatedTanks[tankName];
        return updatedTanks;
      });
    }
  }
  
  // Add this function to create a new tank
  const addNewTank = () => {
    if (!newTankName.trim()) {
      setError('Tank name cannot be empty');
      return;
    }
    
    if (tanksData[newTankName]) {
      setError(`A tank named "${newTankName}" already exists`);
      return;
    }
    
    setTanks(prev => ({
      ...prev,
      [newTankName]: {
        capacity: 100,
        content: []
      }
    }));
    
    setNewTankName('');
    setIsAddingTank(false);
    setError('');
  }
  
  const handleContentChange = (tankName, contentIndex, grade, value) => {
    // Create a copy of the tanks object
    const updatedTanks = { ...tanks }
    
    // Extract current content array for this tank
    const tankContent = [...updatedTanks[tankName].content]
    
    // Convert value to number properly, default to 0 if invalid
    const numValue = grade === "" ? 0 : (parseFloat(value) || 0);
    
    // If this is adding a new grade that wasn't in the content array before
    if (contentIndex >= tankContent.length) {
      if (grade !== "") {
        tankContent.push({ [grade]: numValue })
      }
    } else {
      // Otherwise update existing content
      const existingContent = tankContent[contentIndex]
      const existingGrade = Object.keys(existingContent)[0]
      
      // If grade changed, create new object with new grade
      if (grade !== existingGrade) {
        if (grade !== "") {
          tankContent[contentIndex] = { [grade]: numValue }
        } else {
          // If grade cleared, remove this entry
          tankContent.splice(contentIndex, 1);
        }
      } else {
        // Just update the value for existing grade
        tankContent[contentIndex] = { [grade]: numValue }
      }
    }
    
    // Update the tank with new content
    updatedTanks[tankName].content = tankContent
    
    setTanks(updatedTanks)
  }
  
  const removeContent = (tankName, contentIndex) => {
    setTanks(prev => {
      const tank = { ...prev[tankName] }
      const content = [...tank.content]
      content.splice(contentIndex, 1)
      tank.content = content
      
      return {
        ...prev,
        [tankName]: tank
      }
    })
  }
  
  const addNewContent = (tankName) => {
    setTanks(prev => {
      const tank = { ...prev[tankName] }
      const content = [...tank.content]
      content.push({ "": 0 })  // Default empty grade with 0 volume
      tank.content = content
      
      return {
        ...prev,
        [tankName]: tank
      }
    })
  }
  
  return (
    <div className="space-y-4 max-h-96 overflow-y-auto pr-2">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}
      
      {/* Add new tank form */}
      {isAddingTank && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
          <h3 className="font-medium text-slate-800 mb-3">Add New Tank</h3>
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={newTankName}
              onChange={(e) => setNewTankName(e.target.value)}
              placeholder="Enter tank name"
              className="flex-grow px-3 py-2 border border-slate-300 rounded"
              autoFocus
            />
            <button
              onClick={addNewTank}
              className="px-3 py-2 !bg-emerald-600 text-white rounded hover:bg-green-700"
            >
              Add Tank
            </button>
            <button
              onClick={() => setIsAddingTank(false)}
              className="px-3 py-2 bg-gray-200 text-gray-800 rounded hover:bg-gray-300"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
      
      {/* Add new tank button */}
      {!isAddingTank && (
        <div className="flex justify-end mb-4">
          <button
            onClick={() => setIsAddingTank(true)}
            className="px-3 py-1 !bg-emerald-600 text-white rounded text-sm hover:bg-green-600"
          >
            + Add New Tank
          </button>
        </div>
      )}
      
      {/* Tank list */}
      {Object.entries(tanksData).map(([tankName, tank]) => {
        // Add safety check for tank.content
        const tankContent = tank.content || [];
        
        return (
          <div key={tankName} className="border border-slate-200 rounded-lg p-4">
            <div className="flex justify-between items-center mb-3">
              <div className="flex items-center gap-2">
                <h3 className="font-bold text-slate-800">{tankName}</h3>
                <button
                  onClick={() => deleteTank(tankName)}
                  className="p-1 text-red-500 hover:text-red-700 rounded-full hover:bg-red-50"
                  title="Delete Tank"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                  </svg>
                </button>
              </div>
              <div className="text-sm text-slate-500">
                Capacity: 
                <input
                  type="number"
                  value={tank.capacity || 0}
                  onChange={(e) => handleTankPropertyChange(tankName, 'capacity', parseFloat(e.target.value))}
                  className="ml-1 w-24 px-2 py-1 border border-slate-300 rounded"
                />
              </div>
            </div>
            
            <div className="space-y-2">
              <div className="text-sm font-medium text-slate-700">Tank Contents:</div>
              {tankContent.map((contentItem, idx) => {
                const grade = contentItem ? Object.keys(contentItem)[0] : "";
                const volume = contentItem ? Object.values(contentItem)[0] : 0;
                
                return (
                  <div key={idx} className="flex items-center gap-2">
                    <select
                      value={grade}
                      onChange={(e) => handleContentChange(tankName, idx, e.target.value, volume)}
                      className="flex-grow px-2 py-1.5 border border-slate-300 rounded text-sm"
                    >
                      <option value="">Select grade...</option>
                      {allGrades.length > 0 ? (
                        allGrades.map(g => (
                          <option key={g} value={g}>{g}</option>
                        ))
                      ) : (
                        <option value="" disabled>No crude grades available</option>
                      )}
                    </select>
                    
                    <input
                      type="number"
                      value={volume}
                      onChange={(e) => handleContentChange(tankName, idx, grade, e.target.value)}
                      className="w-24 px-2 py-1.5 border border-slate-300 rounded text-sm"
                      placeholder="Volume"
                    />
                    
                    <button
                      onClick={() => removeContent(tankName, idx)}
                      className="p-1.5 text-red-500 hover:text-red-700"
                      title="Remove"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                );
              })}
              
              <button
                onClick={() => addNewContent(tankName)}
                className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
              >
                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                </svg>
                Add Content
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Vessel Editor Component (replace the current one)
function VesselDataEditor({ vessels, setVessels }) {
  // Ensure vessels is always processed as an array
  let vesselsData = [];
  
  if (vessels) {
    if (Array.isArray(vessels)) {
      vesselsData = vessels;
    } else if (typeof vessels === 'object') {
      // Convert object to array if needed
      vesselsData = Object.values(vessels);
    }
  }
  
  if (vesselsData.length === 0) {
    return <p className="text-slate-500">No vessel data available to edit.</p>
  }

  // Add missing handler functions
  const handleVesselChange = (vesselId, property, value) => {
    setVessels(prev => {
      if (Array.isArray(prev)) {
        return prev.map(vessel => 
          vessel.vessel_id === vesselId 
            ? { ...vessel, [property]: value }
            : vessel
        );
      } else {
        // Handle object format if needed
        return {
          ...prev,
          [vesselId]: {
            ...prev[vesselId],
            [property]: value
          }
        };
      }
    });
  };
  
  const handleCargoChange = (vesselId, cargoIndex, property, value) => {
    setVessels(prev => {
      if (Array.isArray(prev)) {
        return prev.map(vessel => {
          if (vessel.vessel_id === vesselId) {
            const updatedCargo = [...(vessel.cargo || [])];
            if (updatedCargo[cargoIndex]) {
              updatedCargo[cargoIndex] = { 
                ...updatedCargo[cargoIndex],
                [property]: value 
              };
            }
            return { ...vessel, cargo: updatedCargo };
          }
          return vessel;
        });
      } else {
        // Handle object format
        const vessel = {...prev[vesselId]};
        const updatedCargo = [...(vessel.cargo || [])];
        if (updatedCargo[cargoIndex]) {
          updatedCargo[cargoIndex] = { 
            ...updatedCargo[cargoIndex],
            [property]: value 
          };
        }
        return {
          ...prev,
          [vesselId]: {
            ...vessel,
            cargo: updatedCargo
          }
        };
      }
    });
  };
  
  const handleLdrChange = (vesselId, cargoIndex, startDay, endDay) => {
    setVessels(prev => {
      if (Array.isArray(prev)) {
        return prev.map(vessel => {
          if (vessel.vessel_id === vesselId) {
            const updatedCargo = [...(vessel.cargo || [])];
            if (updatedCargo[cargoIndex]) {
              updatedCargo[cargoIndex] = { 
                ...updatedCargo[cargoIndex],
                ldr: { [startDay]: endDay }
              };
            }
            return { ...vessel, cargo: updatedCargo };
          }
          return vessel;
        });
      } else {
        // Handle object format
        const vessel = {...prev[vesselId]};
        const updatedCargo = [...(vessel.cargo || [])];
        if (updatedCargo[cargoIndex]) {
          updatedCargo[cargoIndex] = { 
            ...updatedCargo[cargoIndex],
            ldr: { [startDay]: endDay }
          };
        }
        return {
          ...prev,
          [vesselId]: {
            ...vessel,
            cargo: updatedCargo
          }
        };
      }
    });
  };
  
  const addNewCargo = (vesselId) => {
    setVessels(prev => {
      if (Array.isArray(prev)) {
        return prev.map(vessel => {
          if (vessel.vessel_id === vesselId) {
            return {
              ...vessel,
              cargo: [
                ...(vessel.cargo || []),
                {
                  grade: "",
                  volume: 0,
                  ldr: { 0: 0 },
                  origin: "",
                  vessel_id: vesselId
                }
              ]
            };
          }
          return vessel;
        });
      } else {
        // Handle object format
        return {
          ...prev,
          [vesselId]: {
            ...prev[vesselId],
            cargo: [
              ...(prev[vesselId].cargo || []),
              {
                grade: "",
                volume: 0,
                ldr: { 0: 0 },
                origin: "",
                vessel_id: vesselId
              }
            ]
          }
        };
      }
    });
  };
  
  const removeCargo = (vesselId, cargoIndex) => {
    setVessels(prev => {
      if (Array.isArray(prev)) {
        return prev.map(vessel => {
          if (vessel.vessel_id === vesselId) {
            const updatedCargo = [...(vessel.cargo || [])];
            updatedCargo.splice(cargoIndex, 1);
            return { ...vessel, cargo: updatedCargo };
          }
          return vessel;
        });
      } else {
        // Handle object format
        const vessel = {...prev[vesselId]};
        const updatedCargo = [...(vessel.cargo || [])];
        updatedCargo.splice(cargoIndex, 1);
        return {
          ...prev,
          [vesselId]: {
            ...vessel,
            cargo: updatedCargo
          }
        };
      }
    });
  };

  // Now we can safely use array methods
  const allOrigins = ['Sabah', 'Sarawak', 'Peninsular Malaysia'];
  
  const allGrades = [...new Set(
    vesselsData
      .filter(vessel => vessel && vessel.cargo)
      .flatMap(vessel => 
        vessel.cargo
          .filter(item => item !== null && item !== undefined)
          .map(item => item.grade)
      )
  )].filter(Boolean);

  // Add at the start of VesselDataEditor component
  const getLocationColor = (location) => {
    const locationColors = {
      'Refinery': '#4ade80',
      'Sabah': '#60a5fa',
      'Sarawak': '#c084fc',
      'Peninsular Malaysia': '#f97316'
    };
    return locationColors[location] || '#94a3b8';
  };

  // Add these near the top of your VesselDataEditor function
  useEffect(() => {
    // Log vessels with routes to check if routes exist
    console.log("Vessels with routes:", 
      vesselsData.filter(v => v.route && v.route.length > 0)
        .map(v => `${v.vessel_id} (${v.route?.length || 0} segments)`));
  }, [vesselsData]);

  // Return the component JSX with proper error handling
  return (
    <div className="space-y-6 max-h-96 overflow-y-auto pr-2">
      {vesselsData.map(vessel => (
        <div key={vessel.vessel_id || Math.random()} className="border border-slate-200 rounded-lg p-4">
          <div className="flex justify-between items-center mb-4">
            <h3 className="font-bold text-slate-800">{vessel.vessel_id || "New Vessel"}</h3>
            
            <div className="flex items-center gap-3">
              <div className="text-sm">
                <span className="text-slate-500">Arrival:</span>
                <input
                  type="number"
                  value={vessel.arrival_day || 0}
                  onChange={(e) => handleVesselChange(vessel.vessel_id, 'arrival_day', parseInt(e.target.value) || 0)}
                  className="ml-1 w-16 px-2 py-1 border border-slate-300 rounded"
                />
              </div>
              
              <div className="text-sm">
                <span className="text-slate-500">Capacity:</span>
                <input
                  type="number"
                  value={vessel.capacity || 0}
                  onChange={(e) => handleVesselChange(vessel.vessel_id, 'capacity', parseFloat(e.target.value) || 0)}
                  className="ml-1 w-20 px-2 py-1 border border-slate-300 rounded"
                />
              </div>
            </div>
          </div>
          
          <div className="mb-4">
            <div className="text-sm font-medium text-slate-700 mb-2">Cargo Items:</div>
            
            {/* Handle case where vessel.cargo is undefined */}
            {(vessel.cargo || []).map((cargoItem, idx) => {
              // Get ldr values - with fallbacks for missing or malformed data
              const ldrStartDay = cargoItem.ldr ? Object.keys(cargoItem.ldr)[0] || 0 : 0;
              const ldrEndDay = cargoItem.ldr ? Object.values(cargoItem.ldr)[0] || 0 : 0;
              
              return (
                <div key={idx} className="bg-slate-50 p-3 rounded-lg mb-3 border border-slate-200">
                  <div className="grid grid-cols-2 gap-3 mb-2">
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">Grade</label>
                      <select
                        value={cargoItem.grade || ""}
                        onChange={(e) => handleCargoChange(vessel.vessel_id, idx, 'grade', e.target.value)}
                        className="w-full px-2 py-1.5 border border-slate-300 rounded"
                      >
                        <option value="">Select grade...</option>
                        {allGrades.map(g => (
                          <option key={g} value={g}>{g}</option>
                        ))}
                      </select>
                    </div>
                    
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">Volume</label>
                      <input
                        type="number"
                        value={cargoItem.volume || 0}
                        onChange={(e) => handleCargoChange(vessel.vessel_id, idx, 'volume', parseFloat(e.target.value) || 0)}
                        className="w-full px-2 py-1.5 border border-slate-300 rounded"
                      />
                    </div>
                    
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">Origin</label>
                      <select
                        value={cargoItem.origin || ""}
                        onChange={(e) => handleCargoChange(vessel.vessel_id, idx, 'origin', e.target.value)}
                        className="w-full px-2 py-1.5 border border-slate-300 rounded"
                      >
                        <option value="">Select origin...</option>
                        {allOrigins.map(o => (
                          <option key={o} value={o}>{o}</option>
                        ))}
                      </select>
                    </div>
                    
                    <div>
                      <label className="block text-xs text-slate-500 mb-1">Loading (Start-End)</label>
                      <div className="flex items-center">
                        <input
                          type="number"
                          value={ldrStartDay}
                          onChange={(e) => handleLdrChange(vessel.vessel_id, idx, parseInt(e.target.value) || 0, ldrEndDay)}
                          className="w-16 px-2 py-1.5 border border-slate-300 rounded-l"
                        />
                        <span className="px-2 text-slate-400">-</span>
                        <input
                          type="number"
                          value={ldrEndDay}
                          onChange={(e) => handleLdrChange(vessel.vessel_id, idx, ldrStartDay, parseInt(e.target.value) || 0)}
                          className="w-16 px-2 py-1.5 border border-slate-300 rounded-r"
                        />
                      </div>
                    </div>
                  </div>
                  
                  <button
                    onClick={() => removeCargo(vessel.vessel_id, idx)}
                    className="text-sm text-red-500 hover:text-red-700 flex items-center gap-1"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                    </svg>
                    Remove Cargo
                  </button>
                </div>
              );
            })}
            
            <button
              onClick={() => addNewCargo(vessel.vessel_id)}
              className="text-sm text-blue-600 hover:text-blue-800 flex items-center gap-1"
            >
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
              </svg>
              Add Cargo Item
            </button>
          </div>
          
          <div className="grid grid-cols-2 gap-3">
            <div className="text-sm">
              <span className="text-slate-500">Cost:</span>
              <input
                type="number"
                value={vessel.cost || 0}
                onChange={(e) => handleVesselChange(vessel.vessel_id, 'cost', parseFloat(e.target.value) || 0)}
                className="ml-1 w-24 px-2 py-1 border border-slate-300 rounded"
              />
            </div>
            
            <div className="text-sm">
              <span className="text-slate-500">Days Held:</span>
              <input
                type="number"
                value={vessel.days_held || 0}
                onChange={(e) => handleVesselChange(vessel.vessel_id, 'days_held', parseInt(e.target.value) || 0)}
                className="ml-1 w-16 px-2 py-1 border border-slate-300 rounded"
              />
            </div>
          </div>
          {vessel.route && vessel.route.length > 0 && (
            <div className="mt-4">
              <div className="text-sm font-medium text-slate-700 mb-2 flex items-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-1 text-blue-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                </svg>
                Route Information:
              </div>
              <div className="bg-blue-50 p-3 rounded-lg border border-blue-200">
                {/* Route timeline visualization - make taller and add border */}
                <div className="h-5 relative w-full bg-gray-100 rounded-full overflow-hidden mb-3 border border-gray-300">
                  {/* First determine the maximum day in the route for scaling */}
                  {(() => {
                    // Find last day in route for scaling
                    const lastDay = vessel.route.length > 0 ? 
                      Math.max(...vessel.route.map(segment => segment.day)) :
                      vessel.arrival_day || 30;
                    
                    return vessel.route.map((segment, index) => {
                      // Calculate position based on actual days
                      const startDay = segment.day - segment.travel_days;
                      const endDay = segment.day;
                      const startPercent = (startDay / lastDay) * 100;
                      const widthPercent = ((endDay - startDay) / lastDay) * 100;
                      
                      return (
                        <div 
                          key={index}
                          className="absolute h-full"
                          style={{ 
                            left: `${startPercent}%`, 
                            width: `${widthPercent}%`,
                            background: `linear-gradient(to right, ${getLocationColor(segment.from)}, ${getLocationColor(segment.to)})`
                          }}
                          title={`${segment.from} to ${segment.to} (Day ${startDay} - Day ${endDay})`}
                        />
                      );
                    })
                  })()}
                  
                  {/* Stop markers - also based on actual days */}
                  {(() => {
                    const lastDay = vessel.route.length > 0 ? 
                      Math.max(...vessel.route.map(segment => segment.day)) :
                      vessel.arrival_day || 30;
                    
                    return vessel.route.map((segment, index) => {
                      if (index === 0) return null;
                      const stopDay = segment.day - segment.travel_days;
                      const stopPosition = (stopDay / lastDay) * 100;
                      
                      return (
                        <div 
                          key={`stop-${index}`}
                          className="absolute w-4 h-4 rounded-full border-2 border-white shadow-sm transform -translate-x-1/2 -translate-y-1/2 z-10 flex items-center justify-center"
                          style={{ 
                            left: `${stopPosition}%`, 
                            top: '50%',
                            backgroundColor: getLocationColor(segment.from)
                          }}
                          title={`Stop at ${segment.from} on Day ${stopDay}`}
                        >
                          <div className="w-2 h-2 rounded-full bg-white"></div>
                        </div>
                      );
                    });
                  })()}
                  
                  {/* Show final arrival */}
                  {vessel.arrival_day && (
                    <div
                      className="absolute w-4 h-4 rounded-full bg-green-500 border-2 border-white transform -translate-x-1/2 -translate-y-1/2 z-10 flex items-center justify-center"
                      style={{
                        left: `100%`,
                        top: '50%'
                      }}
                      title={`Arrival at Refinery on Day ${vessel.arrival_day}`}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-2 w-2 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    </div>
                  )}
                </div>

                {/* Day markers */}
                <div className="flex justify-between text-xs text-gray-400 mt-1">
                  <span>Day 0</span>
                  <span>Day {vessel.arrival_day || 30}</span>
                </div>
                
                {/* Route details as text */}
                <div className="space-y-2 mt-3 pt-2 border-t border-slate-200">
                  {vessel.route.map((segment, index) => (
                    <div key={`detail-${index}`} className="flex items-center">
                      <div 
                        className="w-3 h-3 rounded-full mr-2 flex-shrink-0 border border-white shadow-sm" 
                        style={{ backgroundColor: getLocationColor(segment.from) }}
                      ></div>
                      <span className="font-medium">{segment.from} → {segment.to}</span>
                      <span className="ml-2 text-slate-500">
                        (Days {segment.day - segment.travel_days} - {segment.day})
                      </span>
                    </div>
                  ))}
                </div>
                
                <div className="mt-2 text-xs text-slate-500 italic">
                  Route information is generated by the vessel optimizer.
                </div>
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// Add new function for adding a new vessel
function addNewVessel() {
  const timestamp = Date.now();
  setVessels(prev => [
    ...prev,
    {
      vessel_id: `Vessel_${timestamp}`, // Use timestamp for uniqueness
      arrival_day: 0,
      capacity: 0,
      cost: 0,
      cargo: [],
      days_held: 0
    }
  ]);
}

// Add this check before saving a vessel ID edit:

function saveVesselIdEdit(oldId, newId) {
  // Check if the new ID already exists in other vessels
  if (newId !== oldId && vesselsData.some(v => v.vessel_id === newId)) {
    setError(`A vessel with ID "${newId}" already exists. Please choose another ID.`);
    return;
  }
  
  // Proceed with the update if ID is unique
  setVessels(prev => prev.map(v => 
    v.vessel_id === oldId ? {...v, vessel_id: newId} : v
  ));
  setEditingVesselId(null);
}

// Add new PlantDataEditor component
function PlantDataEditor({ plants, setPlants }) {
  // Since plants is a single object, not a collection
  const plant = plants || {};
  
  if (Object.keys(plant).length === 0) {
    return <p className="text-slate-500">No plant data available to edit.</p>
  }

  const handlePlantChange = (property, value) => {
    setPlants(prev => ({
      ...prev,
      [property]: property === 'capacity' || property === 'base_crude_capacity' || property === 'max_inventory' 
        ? parseFloat(value) 
        : value
    }));
  };

  return (
    <div className="space-y-4 max-h-96 overflow-y-auto pr-2">
      <div className="bg-white rounded-lg border border-slate-200 p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Refinery Configuration</h3>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">
              Plant Name
            </label>
            <input
              type="text"
              value={plant.name || ''}
              onChange={(e) => handlePlantChange('name', e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">
              Processing Capacity (kbbl/day)
            </label>
            <input
              type="number"
              step="0.1"
              value={plant.capacity || 0}
              onChange={(e) => handlePlantChange('capacity', e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">
              Base Crude Capacity (kbbl/day)
            </label>
            <input
              type="number"
              step="0.1"
              value={plant.base_crude_capacity || 0}
              onChange={(e) => handlePlantChange('base_crude_capacity', e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-600 mb-1">
              Maximum Inventory (kbbl)
            </label>
            <input
              type="number"
              step="0.1"
              value={plant.max_inventory || 0}
              onChange={(e) => handlePlantChange('max_inventory', e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
        
        <div className="mt-6 bg-blue-50 p-4 rounded-md text-sm text-blue-800">
          <div className="flex items-start">
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2 text-blue-500 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p>
              <strong>Note:</strong> These values affect the refinery's daily processing capabilities and storage limits. Capacity values are measured in thousands of barrels per day (kbbl/day).
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// Replace the current CrudeDataEditor component with this one:

function CrudeDataEditor({ crudes, setCrudes }) {
  const crudesData = crudes || {};
  const [isAddingCrude, setIsAddingCrude] = useState(false);
  const [newCrude, setNewCrude] = useState({ name: '', margin: 0, origin: 'Terminal1' });
  const [editingName, setEditingName] = useState(null);
  const [tempName, setTempName] = useState('');
  const [error, setError] = useState('');
  
  if (Object.keys(crudesData).length === 0 && !isAddingCrude) {
    return (
      <div className="text-center p-8">
        <p className="text-slate-500 mb-4">No crude data available.</p>
        <button
          onClick={() => setIsAddingCrude(true)}
          className="px-4 py-2 !bg-emerald-600 text-white rounded hover:bg-green-600"
        >
          + Add First Crude
        </button>
      </div>
    );
  }

  const handleCrudeChange = (crudeId, property, value) => {
    setCrudes(prev => ({
      ...prev,
      [crudeId]: {
        ...prev[crudeId],
        [property]: property === 'margin' ? parseFloat(value) : value,
        name: crudeId // Ensure name matches the key
      }
    }));
  };
  
  const startEditName = (crudeId) => {
    setEditingName(crudeId);
    setTempName(crudeId);
    setError('');
  };
  
  const cancelEditName = () => {
    setEditingName(null);
    setTempName('');
    setError('');
  };
  
  const saveEditName = (oldCrudeId) => {
    // Check if the new name already exists
    if (tempName !== oldCrudeId && crudesData[tempName]) {
      setError(`A crude named "${tempName}" already exists`);
      return;
    }
    
    if (!tempName.trim()) {
      setError('Crude name cannot be empty');
      return;
    }
    
    // Create new object with updated key
    const updatedCrudes = { ...crudesData };
    updatedCrudes[tempName] = { 
      ...updatedCrudes[oldCrudeId],
      name: tempName
    };
    
    // Delete old key if name changed
    if (tempName !== oldCrudeId) {
      delete updatedCrudes[oldCrudeId];
    }
    
    setCrudes(updatedCrudes);
    setEditingName(null);
    setTempName('');
    setError('');
  };
  
  const addNewCrude = () => {
    setIsAddingCrude(true);
    setNewCrude({ name: '', margin: 0, origin: 'Peninsular Malaysia' });
    setError('');
  };
  
  const handleNewCrudeChange = (property, value) => {
    setNewCrude(prev => ({
      ...prev,
      [property]: property === 'margin' ? parseFloat(value) : value
    }));
  };
  
  const cancelAddCrude = () => {
    setIsAddingCrude(false);
    setNewCrude({ name: '', margin: 0, origin: 'Peninsular Malaysia' });
    setError('');
  };
  
  const saveNewCrude = () => {
    if (!newCrude.name.trim()) {
      setError('Crude name cannot be empty');
      return;
    }
    
    if (crudesData[newCrude.name]) {
      setError(`A crude named "${newCrude.name}" already exists`);
      return;
    }
    
    setCrudes(prev => ({
      ...prev,
      [newCrude.name]: {
        name: newCrude.name,
        margin: newCrude.margin,
        origin: newCrude.origin
      }
    }));
    
    setIsAddingCrude(false);
    setNewCrude({ name: '', margin: 0, origin: 'Terminal1' });
    setError('');
  };
  
  const deleteCrude = (crudeId) => {
    if (confirm(`Are you sure you want to delete ${crudeId}?`)) {
      setCrudes(prev => {
        const copy = {...prev};
        delete copy[crudeId];
        return copy;
      });
    }
  };

  const terminals = ['Sabah', 'Sarawak', 'Peninsular Malaysia'];

  return (
    <div className="space-y-4 max-h-96 overflow-y-auto pr-2">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}
      
      <div className="flex justify-end mb-4">
        {!isAddingCrude && (
          <button
            onClick={addNewCrude}
            className="px-3 py-1 !bg-emerald-600 text-white rounded text-sm hover:bg-green-600"
          >
            + Add New Crude
          </button>
        )}
      </div>
      
      {isAddingCrude && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
          <h3 className="font-bold text-slate-800 mb-3">Add New Crude</h3>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Name</label>
              <input
                type="text"
                value={newCrude.name}
                onChange={(e) => handleNewCrudeChange('name', e.target.value)}
                className="w-full px-2 py-1 border border-slate-300 rounded"
                placeholder="Crude name"
                autoFocus
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Margin ($/bbl)</label>
              <input
                type="number"
                step="0.1"
                value={newCrude.margin}
                onChange={(e) => handleNewCrudeChange('margin', e.target.value)}
                className="w-full px-2 py-1 border border-slate-300 rounded"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Origin</label>
              <select
                value={newCrude.origin}
                onChange={(e) => handleNewCrudeChange('origin', e.target.value)}
                className="w-full px-2 py-1 border border-slate-300 rounded"
              >
                {terminals.map(terminal => (
                  <option key={terminal} value={terminal}>{terminal}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <button
              onClick={cancelAddCrude}
              className="px-3 py-1 bg-gray-200 text-gray-800 rounded text-sm hover:bg-gray-300"
            >
              Cancel
            </button>
            <button
              onClick={saveNewCrude}
              className="px-3 py-1 !bg-emerald-600 text-white rounded text-sm hover:bg-blue-700"
            >
              Save Crude
            </button>
          </div>
        </div>
      )}
      
      <table className="min-w-full divide-y divide-slate-200 border border-slate-200 rounded-lg overflow-hidden">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Name</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Margin ($/bbl)</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Origin</th>
            <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-slate-100">
          {Object.entries(crudesData).map(([crudeId, crude]) => (
            <tr key={crudeId}>
              <td className="px-6 py-4 whitespace-nowrap">
                {editingName === crudeId ? (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={tempName}
                      onChange={(e) => setTempName(e.target.value)}
                      className="w-full px-2 py-1 border border-blue-300 rounded"
                      autoFocus
                    />
                    <button 
                      onClick={() => saveEditName(crudeId)}
                      className="text-green-600 hover:text-green-800"
                      title="Save name"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    </button>
                    <button 
                      onClick={cancelEditName}
                      className="text-red-600 hover:text-red-800"
                      title="Cancel"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center">
                    <span className="text-sm font-medium text-slate-700">{crudeId}</span>
                    <button
                      onClick={() => startEditName(crudeId)}
                      className="ml-2 text-blue-500 hover:text-blue-700"
                      title="Edit name"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                      </svg>
                    </button>
                  </div>
                )}
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <input
                  type="number"
                  step="0.1"
                  value={crude.margin || 0}
                  onChange={(e) => handleCrudeChange(crudeId, 'margin', e.target.value)}
                  className="w-24 px-2 py-1 border border-slate-300 rounded"
                />
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <select
                  value={crude.origin || ''}
                  onChange={(e) => handleCrudeChange(crudeId, 'origin', e.target.value)}
                  className="px-2 py-1 border border-slate-300 rounded"
                >
                  {terminals.map(terminal => (
                    <option key={terminal} value={terminal}>{terminal}</option>
                  ))}
                </select>
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-right">
                <button
                  onClick={() => deleteCrude(crudeId)}
                  className="text-red-500 hover:text-red-700"
                  title="Delete crude"
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Replace the current RecipeDataEditor function with this one:

function RecipeDataEditor({ recipes, setRecipes, crudes }) {
  const recipesData = recipes || {};
  const crudesData = crudes || {};
  const [isAddingRecipe, setIsAddingRecipe] = useState(false);
  const [newRecipe, setNewRecipe] = useState({ 
    name: '', 
    primary_grade: '',  // Changed from primaryGrade to match your data structure
    secondary_grade: null,  // Changed from secondaryGrades array to match data
    max_rate: 250,
    primary_fraction: 0.7
  });
  const [error, setError] = useState(null);
  
  // Define crudeOptions consistently with the proper naming
  const crudeOptions = Object.keys(crudesData).filter(Boolean);
  
  if (Object.keys(recipesData).length === 0 && !isAddingRecipe) {
    return (
      <div className="text-center p-8">
        <p className="text-slate-500 mb-4">No recipe data available.</p>
        <button
          onClick={() => setIsAddingRecipe(true)}
          className="px-4 py-2 !bg-emerald-600 text-white rounded hover:bg-green-600"
        >
          + Add First Recipe
        </button>
      </div>
    );
  }

  const handleRecipeChange = (recipeId, property, value) => {
    setRecipes(prev => ({
      ...prev,
      [recipeId]: {
        ...prev[recipeId],
        [property]: property === 'max_rate' || property === 'primary_fraction' ? parseFloat(value) : value
      }
    }));
  };
  
  const handleNewRecipeChange = (property, value) => {
    setNewRecipe(prev => ({
      ...prev,
      [property]: property === 'max_rate' || property === 'primary_fraction' ? parseFloat(value) : value
    }));
  };
  
  const addNewRecipe = () => {
    setIsAddingRecipe(true);
    setNewRecipe({ name: '', primaryGrade: '', secondaryGrades: [] });
    setError(null);
  };
  
  const cancelAddRecipe = () => {
    setIsAddingRecipe(false);
    setNewRecipe({ name: '', primaryGrade: '', secondaryGrades: [] });
    setError(null);
  };
  
  const saveNewRecipe = () => {
    if (!newRecipe.name.trim()) {
      setError('Recipe name cannot be empty');
      return;
    }

    if (recipes[newRecipe.name]) {
      setError(`A recipe named "${newRecipe.name}" already exists`);
      return;
    }

    if (!newRecipe.primaryGrade) {
      setError('Primary grade is required');
      return;
    }

    setRecipes((prev) => ({
      ...prev,
      [newRecipe.name]: {
        name: newRecipe.name,
        primaryGrade: newRecipe.primaryGrade,
        secondaryGrades: newRecipe.secondaryGrades || [],
      },
    }));

    setNewRecipe({ name: '', primaryGrade: '', secondaryGrades: [] });
    setError(null);
  };

  const deleteRecipe = (recipeId) => {
    if (confirm(`Are you sure you want to delete the recipe "${recipeId}"?`)) {
      setRecipes((prev) => {
        const updatedRecipes = { ...prev };
        delete updatedRecipes[recipeId];
        return updatedRecipes;
      });
    }
  };

  return (
    <div className="space-y-4 max-h-96 overflow-y-auto pr-2">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}
      
      <div className="flex justify-end mb-4">
        {!isAddingRecipe && (
          <button
            onClick={addNewRecipe}
            className="px-3 py-1 !bg-emerald-600 text-white rounded text-sm hover:bg-green-600"
          >
            + Add New Recipe
          </button>
        )}
      </div>
      
      {isAddingRecipe && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
          <h3 className="font-bold text-slate-800 mb-3">Add New Recipe</h3>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Name</label>
              <input
                type="text"
                value={newRecipe.name}
                onChange={(e) => handleNewRecipeChange('name', e.target.value)}
                className="w-full px-2 py-1 border border-slate-300 rounded"
                placeholder="Recipe name"
                autoFocus
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Max Rate (kbbl/day)</label>
              <input
                type="number"
                step="0.1"
                min="0"
                value={newRecipe.max_rate}
                onChange={(e) => handleNewRecipeChange('max_rate', e.target.value)}
                className="w-full px-2 py-1 border border-slate-300 rounded"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">
                Primary Grade <span className="text-red-500">*</span>
              </label>
              <select
                value={newRecipe.primary_grade || ''}
                onChange={(e) => handleNewRecipeChange('primary_grade', e.target.value)}
                className="w-full px-2 py-1 border border-slate-300 rounded"
              >
                <option value="">Select primary grade</option>
                {crudeOptions.map(crude => (
                  <option key={crude} value={crude}>{crude}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">
                Primary Fraction (0-1)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="1"
                value={newRecipe.primary_fraction}
                onChange={(e) => handleNewRecipeChange('primary_fraction', e.target.value)}
                className="w-full px-2 py-1 border border-slate-300 rounded"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">
                Secondary Grade <span className="text-gray-400">(optional)</span>
              </label>
              <select
                value={newRecipe.secondary_grade || ''}
                onChange={(e) => handleNewRecipeChange('secondary_grade', e.target.value)}
                className="w-full px-2 py-1 border border-slate-300 rounded"
              >
                <option value="">None</option>
                {crudeOptions
                  .filter(crude => crude !== newRecipe.primary_grade)
                  .map(crude => (
                    <option key={crude} value={crude}>{crude}</option>
                  ))
                }
              </select>
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <button
              onClick={cancelAddRecipe}
              className="px-3 py-1 bg-gray-200 text-gray-800 rounded text-sm hover:bg-gray-300"
            >
              Cancel
            </button>
            <button
              onClick={saveNewRecipe}
              className="px-3 py-1 !bg-emerald-600 text-white rounded text-sm hover:bg-blue-700"
            >
              Save Recipe
            </button>
          </div>
        </div>
      )}
      
      <table className="min-w-full divide-y divide-slate-200 border border-slate-200 rounded-lg overflow-hidden">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Name</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Primary Grade</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Secondary Grade</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Max Rate (kbbl/day)</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Primary Fraction</th>
            <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-slate-100">
          {Object.entries(recipesData).map(([recipeId, recipe]) => (
            <tr key={recipeId}>
              <td className="px-6 py-4 whitespace-nowrap">
                <div className="text-sm font-medium text-slate-700">{recipeId}</div>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <select
                  value={recipe.primary_grade || ''}
                  onChange={(e) => handleRecipeChange(recipeId, 'primary_grade', e.target.value)}
                  className="px-2 py-1 border border-slate-300 rounded"
                >
                  <option value="">Select primary grade</option>
                  {crudeOptions.map(crude => (
                    <option key={crude} value={crude}>{crude}</option>
                  ))}
                </select>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <select
                  value={recipe.secondary_grade || ''}
                  onChange={(e) => handleRecipeChange(recipeId, 'secondary_grade', e.target.value === '' ? null : e.target.value)}
                  className="px-2 py-1 border border-slate-300 rounded"
                >
                  <option value="">None</option>
                  {crudeOptions
                    .filter(crude => crude !== recipe.primary_grade)
                    .map(crude => (
                      <option key={crude} value={crude}>{crude}</option>
                    ))
                  }
                </select>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={recipe.max_rate || 0}
                  onChange={(e) => handleRecipeChange(recipeId, 'max_rate', e.target.value)}
                  className="w-24 px-2 py-1 border border-slate-300 rounded"
                />
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  max="1"
                  value={recipe.primary_fraction || 0}
                  onChange={(e) => handleRecipeChange(recipeId, 'primary_fraction', e.target.value)}
                  className="w-20 px-2 py-1 border border-slate-300 rounded"
                />
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-right">
                <button
                  onClick={() => deleteRecipe(recipeId)}
                  className="text-red-500 hover:text-red-700"
                  title="Delete recipe"
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Replace the current RouteDataEditor function with this one:

function RouteDataEditor({ routes, setRoutes }) {
  const routesData = routes || {};
  const [isAddingRoute, setIsAddingRoute] = useState(false);
  const [newRoute, setNewRoute] = useState({
    routeId: '',
    origin: 'Terminal1',
    destination: 'Refinery',
    time_travel: 5.0
  });
  const [error, setError] = useState('');
  const [editingRouteId, setEditingRouteId] = useState(null);
  const [tempRouteId, setTempRouteId] = useState('');
  
  if (Object.keys(routesData).length === 0 && !isAddingRoute) {
    return (
      <div className="text-center p-8">
        <p className="text-slate-500 mb-4">No route data available.</p>
        <button
          onClick={() => setIsAddingRoute(true)}
          className="px-4 py-2 !bg-emerald-600 text-white rounded hover:bg-green-600"
        >
          + Add First Route
        </button>
      </div>
    );
  }

  function handleRouteChange(routeId, property, value) {
    setRoutes(prev => ({
      ...prev,
      [routeId]: {
        ...prev[routeId],
        [property]: property === 'time_travel' ? parseFloat(value) : value
      }
    }));
  }
  
  function handleNewRouteChange(property, value) {
    setNewRoute(prev => ({
      ...prev,
      [property]: property === 'time_travel' ? parseFloat(value) : value
    }));
  }
  
  function addNewRoute() {
    const suggestedRouteId = `${newRoute.origin}_${newRoute.destination}`;
    setIsAddingRoute(true);
    setNewRoute({
      routeId: suggestedRouteId,
      origin: 'Terminal1',
      destination: 'Refinery',
      time_travel: 5.0
    });
    setError('');
  }
  
  function saveNewRoute() {
    if (!newRoute.routeId.trim()) {
      setError('Route ID is required');
      return;
    }
    
    if (!newRoute.origin || !newRoute.destination) {
      setError('Origin and destination are required');
      return;
    }
    
    // Check if route already exists
    if (routesData[newRoute.routeId]) {
      setError(`A route with ID "${newRoute.routeId}" already exists`);
      return;
    }
    
    setRoutes(prev => ({
      ...prev,
      [newRoute.routeId]: {
        origin: newRoute.origin,
        destination: newRoute.destination,
        time_travel: newRoute.time_travel
      }
    }));
    
    setIsAddingRoute(false);
    setError('');
  }
  
  function cancelAddRoute() {
    setIsAddingRoute(false);
    setError('');
  }
  
  function deleteRoute(routeId) {
    if (confirm(`Are you sure you want to delete route ${routeId}?`)) {
      setRoutes(prev => {
        const copy = {...prev};
        delete copy[routeId];
        return copy;
      });
    }
  }
  
  function startEditRouteId(routeId) {
    setEditingRouteId(routeId);
    setTempRouteId(routeId);
    setError('');
  }
  
  function cancelEditRouteId() {
    setEditingRouteId(null);
    setTempRouteId('');
    setError('');
  }
  
  function saveEditRouteId(oldRouteId) {
    // Check if route ID is empty
    if (!tempRouteId.trim()) {
      setError('Route ID cannot be empty');
      return;
    }
    
    // Check if new ID already exists and is not the same as the current one
    if (tempRouteId !== oldRouteId && routesData[tempRouteId]) {
      setError(`A route with ID "${tempRouteId}" already exists`);
      return;
    }
    
    // Create new object with updated key
    const updatedRoutes = { ...routesData };
    updatedRoutes[tempRouteId] = { 
      ...updatedRoutes[oldRouteId]
    };
    
    // Delete old key if ID changed
    if (tempRouteId !== oldRouteId) {
      delete updatedRoutes[oldRouteId];
    }
    
    setRoutes(updatedRoutes);
    setEditingRouteId(null);
    setTempRouteId('');
    setError('');
  }

  const terminals = ['Sabah', 'Sarawak', 'Peninsular Malaysia', 'Refinery'];

  return (
    <div className="space-y-4 max-h-96 overflow-y-auto pr-2">
      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}
      
      <div className="flex justify-end mb-4">
        {!isAddingRoute && (
          <button
            onClick={addNewRoute}
            className="px-3 py-1 !bg-emerald-600 text-white rounded text-sm hover:bg-green-600"
          >
            + Add New Route
          </button>
        )}
      </div>
      
      {isAddingRoute && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
          <h3 className="font-bold text-slate-800 mb-3">Add New Route</h3>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Route ID</label>
              <input
                type="text"
                value={newRoute.routeId}
                onChange={(e) => handleNewRouteChange('routeId', e.target.value)}
                className="w-full px-2 py-1 border border-slate-300 rounded"
                placeholder="Route identifier"
                autoFocus
              />
            </div>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-xs text-slate-500 mb-1">Origin</label>
              <select
                value={newRoute.origin}
                onChange={(e) => {
                  const origin = e.target.value;
                  handleNewRouteChange('origin', origin);
                  // Optionally suggest updating the route ID
                  const suggestedRouteId = `${origin}_${newRoute.destination}`;
                  handleNewRouteChange('routeId', suggestedRouteId);
                }}
                className="w-full px-2 py-1 border border-slate-300 rounded"
              >
                {terminals.map(terminal => (
                  <option key={terminal} value={terminal}>{terminal}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Destination</label>
              <input
                type="text"
                value={newRoute.destination}
                onChange={(e) => {
                  const destination = e.target.value;
                  handleNewRouteChange('destination', destination);
                  // Optionally suggest updating the route ID
                  const suggestedRouteId = `${newRoute.origin}_${destination}`;
                  handleNewRouteChange('routeId', suggestedRouteId);
                }}
                className="w-full px-2 py-1 border border-slate-300 rounded"
                placeholder="e.g. Refinery"
              />
            </div>
            <div>
              <label className="block text-xs text-slate-500 mb-1">Travel Time (days)</label>
              <input
                type="number"
                step="0.1"
                min="0"
                value={newRoute.time_travel}
                onChange={(e) => handleNewRouteChange('time_travel', e.target.value)}
                className="w-full px-2 py-1 border border-slate-300 rounded"
              />
            </div>
          </div>
          <div className="flex justify-end gap-2 mt-4">
            <button
              onClick={cancelAddRoute}
              className="px-3 py-1 bg-gray-200 text-gray-800 rounded text-sm hover:bg-gray-300"
            >
              Cancel
            </button>
            <button
              onClick={saveNewRoute}
              className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
            >
              Save Route
            </button>
          </div>
        </div>
      )}
      
      <table className="min-w-full divide-y divide-slate-200 border border-slate-200 rounded-lg overflow-hidden">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Route ID</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Origin</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Destination</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Travel Time (days)</th>
            <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-slate-100">
          {Object.entries(routesData).map(([routeId, route]) => (
            <tr key={routeId}>
              <td className="px-6 py-4 whitespace-nowrap">
                {editingRouteId === routeId ? (
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={tempRouteId}
                      onChange={(e) => setTempRouteId(e.target.value)}
                      className="w-full px-2 py-1 border border-blue-300 rounded"
                      autoFocus
                    />
                    <button 
                      onClick={() => saveEditRouteId(routeId)}
                      className="text-green-600 hover:text-green-800"
                      title="Save ID"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    </button>
                    <button 
                      onClick={cancelEditRouteId}
                      className="text-red-600 hover:text-red-800"
                      title="Cancel"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center">
                    <span className="text-sm font-medium text-slate-700">{routeId}</span>
                    <button
                      onClick={() => startEditRouteId(routeId)}
                      className="ml-2 text-blue-500 hover:text-blue-700"
                      title="Edit ID"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                      </svg>
                    </button>
                  </div>
                )}
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <select
                  value={route.origin || ''}
                  onChange={(e) => handleRouteChange(routeId, 'origin', e.target.value)}
                  className="px-2 py-1 border border-slate-300 rounded w-32"
                >
                  {terminals.map(terminal => (
                    <option key={terminal} value={terminal}>{terminal}</option>
                  ))}
                </select>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <input
                  type="text"
                  value={route.destination || ''}
                  onChange={(e) => handleRouteChange(routeId, 'destination', e.target.value)}
                  className="px-2 py-1 border border-slate-300 rounded w-40"
                />
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={route.time_travel || 0}
                  onChange={(e) => handleRouteChange(routeId, 'time_travel', e.target.value)}
                  className="px-2 py-1 border border-slate-300 rounded w-24"
                />
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-right">
                <button
                  onClick={() => deleteRoute(routeId)}
                  className="text-red-500 hover:text-red-700"
                  title="Delete route"
                  disabled={editingRouteId === routeId}
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      
      <div className="bg-blue-50 border border-blue-200 text-blue-800 p-4 rounded text-sm mt-4">
        <div className="flex items-start">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <p className="font-medium mb-1">About Route IDs</p>
            <p>You can now directly edit route IDs. By default, the system suggests IDs in the format "Origin_Destination" but you can customize them as needed.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// Add new VesselTypeDataEditor component
function VesselTypeDataEditor({ vesselTypes, setVesselTypes }) {
  const vesselTypesData = Array.isArray(vesselTypes) ? vesselTypes : [];
  
  if (vesselTypesData.length === 0) {
    return (
      <div className="text-center p-8">
        <p className="text-slate-500 mb-4">No vessel type data available.</p>
        <button
          onClick={addNewVesselType}
          className="px-4 py-2 !bg-emerald-600 text-white rounded hover:bg-green-600"
        >
          + Add First Vessel Type
        </button>
      </div>
    );
  }

  function handleVesselTypeChange(index, property, value) {
    setVesselTypes(prev => {
      const updatedTypes = [...prev];
      updatedTypes[index] = {
        ...updatedTypes[index],
        [property]: property === 'capacity' || property === 'cost' ? parseFloat(value) : value
      };
      return updatedTypes;
    });
  }
  
  function addNewVesselType() {
    setVesselTypes(prev => [
      ...prev,
      {
        name: `Vessel Type ${prev.length + 1}`,
        capacity: 0,
        cost: 0
      }
    ]);
  }
  
  function deleteVesselType(index) {
    if (confirm('Are you sure you want to delete this vessel type?')) {
      setVesselTypes(prev => {
        const updatedTypes = [...prev];
        updatedTypes.splice(index, 1);
        return updatedTypes;
      });
    }
  }

  return (
    <div className="space-y-4 max-h-96 overflow-y-auto pr-2">
      <div className="flex justify-end mb-4">
        <button
          onClick={addNewVesselType}
          className="px-3 py-1 !bg-emerald-600 text-white rounded text-sm hover:bg-green-600"
        >
          + Add New Vessel Type
        </button>
      </div>
      
      <table className="min-w-full divide-y divide-slate-200 border border-slate-200 rounded-lg overflow-hidden">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Name</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Capacity (kbbl)</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Cost ($)</th>
            <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-slate-100">
          {vesselTypesData.map((vesselType, index) => (
            <tr key={index}>
              <td className="px-6 py-4 whitespace-nowrap">
                <input
                  type="text"
                  value={vesselType.name || ''}
                  onChange={(e) => handleVesselTypeChange(index, 'name', e.target.value)}
                  className="px-2 py-1 border border-slate-300 rounded w-40"
                />
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <input
                  type="number"
                  value={vesselType.capacity || 0}
                  onChange={(e) => handleVesselTypeChange(index, 'capacity', e.target.value)}
                  className="px-2 py-1 border border-slate-300 rounded w-32"
                />
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <input
                  type="number"
                  value={vesselType.cost || 0}
                  onChange={(e) => handleVesselTypeChange(index, 'cost', e.target.value)}
                  className="px-2 py-1 border border-slate-300 rounded w-32"
                />
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-right">
                <button
                  onClick={() => deleteVesselType(index)}
                  className="text-red-500 hover:text-red-700"
                  title="Delete vessel type"
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Add these new editor components

// Feedstock Parcels Editor
function FeedstockParcelEditor({ parcels, setParcels }) {
  // Handle either array or object format
  let parcelsData = [];
  
  if (parcels) {
    if (Array.isArray(parcels)) {
      parcelsData = parcels;
    } else if (typeof parcels === 'object') {
      // Convert object to array
      parcelsData = Object.values(parcels);
    }
  }
  
  if (parcelsData.length === 0) {
    return (
      <div className="text-center p-8">
        <p className="text-slate-500 mb-4">No feedstock parcel data available.</p>
        <button
          onClick={() => addNewParcel()}
          className="px-4 py-2 !bg-emerald-600 text-white rounded hover:bg-green-600"
        >
          + Add First Parcel
        </button>
      </div>
    );
  }
  
  function handleParcelChange(index, property, value) {
    setParcels(prev => {
      const updatedParcels = [...prev];
      updatedParcels[index] = {
        ...updatedParcels[index],
        [property]: property === 'volume' ? parseFloat(value) : value
      };
      return updatedParcels;
    });
  }
  
  function addNewParcel() {
    setParcels(prev => [
      ...prev,
      {
        grade: "",
        volume: 0,
        origin: "Peninsular Malaysia",
        available_from: 0,
        expiry: 30
      }
    ]);
  }
  
  function deleteParcel(index) {
    if (confirm('Are you sure you want to delete this parcel?')) {
      setParcels(prev => {
        const updatedParcels = [...prev];
        updatedParcels.splice(index, 1);
        return updatedParcels;
      });
    }
  }
  
  // Get all unique grades and origins for dropdown options
  const allGrades = [...new Set(parcelsData.map(parcel => parcel.grade))].filter(Boolean);
  const origins = ['Peninsular Malaysia', 'Sabah', 'Sarawak'];

  return (
    <div className="space-y-4 max-h-96 overflow-y-auto pr-2">
      <div className="flex justify-end mb-4">
        <button
          onClick={addNewParcel}
          className="px-3 py-1 !bg-emerald-600 text-white rounded text-sm hover:bg-green-600"
        >
          + Add New Parcel
        </button>
      </div>
      
      <table className="min-w-full divide-y divide-slate-200 border border-slate-200 rounded-lg overflow-hidden">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Grade</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Volume (kbbl)</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Origin</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Available From (day)</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Expiry (day)</th>
            <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-slate-100">
          {parcelsData.map((parcel, index) => (
            <tr key={index}>
              <td className="px-6 py-4 whitespace-nowrap">
                <input
                  type="text"
                  list="grades-list"
                  value={parcel.grade || ''}
                  onChange={(e) => handleParcelChange(index, 'grade', e.target.value)}
                  className="px-2 py-1 border border-slate-300 rounded w-40"
                />
                <datalist id="grades-list">
                  {allGrades.map(grade => (
                    <option key={grade} value={grade} />
                  ))}
                </datalist>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <input
                  type="number"
                  step="0.1"
                  value={parcel.volume || 0}
                  onChange={(e) => handleParcelChange(index, 'volume', e.target.value)}
                  className="px-2 py-1 border border-slate-300 rounded w-32"
                />
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <select
                  value={parcel.origin || ''}
                  onChange={(e) => handleParcelChange(index, 'origin', e.target.value)}
                  className="px-2 py-1 border border-slate-300 rounded w-40"
                >
                  {origins.map(origin => (
                    <option key={origin} value={origin}>{origin}</option>
                  ))}
                </select>
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <input
                  type="number"
                  value={parcel.available_from || 0}
                  onChange={(e) => handleParcelChange(index, 'available_from', parseInt(e.target.value) || 0)}
                  className="px-2 py-1 border border-slate-300 rounded w-24"
                />
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <input
                  type="number"
                  value={parcel.expiry || 30}
                  onChange={(e) => handleParcelChange(index, 'expiry', parseInt(e.target.value) || 30)}
                  className="px-2 py-1 border border-slate-300 rounded w-24"
                />
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-right">
                <button
                  onClick={() => deleteParcel(index)}
                  className="text-red-500 hover:text-red-700"
                  title="Delete parcel"
                >
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      
      <div className="bg-blue-50 border border-blue-200 text-blue-800 p-4 rounded text-sm mt-4">
        <div className="flex items-start">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <p className="font-medium mb-1">About Feedstock Parcels</p>
            <p>Feedstock parcels represent available crude supplies that can be purchased for refining operations. Available From indicates the earliest day the parcel can be used, and Expiry indicates when the offer expires.</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// Feedstock Requirements Editor
function FeedstockRequirementEditor({ requirements, setRequirements, crudes }) {
  // Handle either array or object format
  let requirementsData = [];
  const [loadedCrudes, setLoadedCrudes] = useState(crudes || {});
  const [isLoading, setIsLoading] = useState(!crudes);
  
  useEffect(() => {
    const fetchCrudes = async () => {
      try {
        setIsLoading(true);
        const response = await axios.get('/api/data');
        console.log("API response for crudes:", response.data);
        if (response.data && response.data.crudes) {
          setLoadedCrudes(response.data.crudes);
          console.log("Set loaded crudes:", response.data.crudes);
        }
      } catch (err) {
        console.error("Error loading crude data:", err);
      } finally {
        setIsLoading(false);
      }
    };
    
    if (!crudes || Object.keys(crudes || {}).length === 0) {
      console.log("No crudes provided, fetching from API");
      fetchCrudes();
    } else {
      console.log("Using provided crudes:", crudes);
      setLoadedCrudes(crudes);
    }
  }, [crudes]);
  
  // Use loaded crudes or passed crudes
  const crudesData = Object.keys(loadedCrudes).length > 0 ? loadedCrudes : (crudes || {});
  
  // Extract crudes options from the crudes prop
  const crudeOptions = Object.keys(crudesData).filter(Boolean);
  console.log("Available crude options:", crudeOptions);
  
  // Convert requirements to array if it's an object
  if (requirements) {
    if (Array.isArray(requirements)) {
      requirementsData = requirements;
    } else if (typeof requirements === 'object') {
      // Convert object to array with ID included
      requirementsData = Object.entries(requirements).map(([id, req]) => ({
        id,
        ...req
      }));
    }
  }
  
  if (requirementsData.length === 0) {
    return (
      <div className="text-center p-8">
        <p className="text-slate-500 mb-4">No feedstock requirement data available.</p>
        <button
          onClick={() => addNewRequirement()}
          className="px-4 py-2 !bg-emerald-600 text-white rounded hover:bg-green-600"
        >
          + Add First Requirement
        </button>
      </div>
    );
  }
  
  function handleRequirementChange(index, property, value) {
    setRequirements(prev => {
      const updatedRequirements = [...prev];
      updatedRequirements[index] = {
        ...updatedRequirements[index],
        [property]: property === 'volume' ? parseFloat(value) : value
      };
      return updatedRequirements;
    });
  }
  
  // New function to handle allowed_ldr changes
  function handleLdrChange(index, startDay, endDay) {
    setRequirements(prev => {
      const updatedRequirements = [...prev];
      updatedRequirements[index] = {
        ...updatedRequirements[index],
        allowed_ldr: { [startDay]: endDay }
      };
      return updatedRequirements;
    });
  }
  
  function addNewRequirement() {
    const nextId = `Requirement_${(requirementsData.length + 1).toString().padStart(3, '0')}`;
    
    if (Array.isArray(requirements)) {
      setRequirements(prev => [
        ...prev,
        {
          id: nextId,
          grade: crudeOptions.length > 0 ? crudeOptions[0] : "",
          volume: 0,
          origin: "Peninsular Malaysia",
          allowed_ldr: { "15": 25 },
          required_arrival_by: 30
        }
      ]);
    } else {
      // Handle object format
      setRequirements(prev => ({
        ...prev,
        [nextId]: {
          grade: crudeOptions.length > 0 ? crudeOptions[0] : "",
          volume: 0,
          origin: "Peninsular Malaysia",
          allowed_ldr: { "15": 25 },
          required_arrival_by: 30
        }
      }));
    }
  }
  
  function deleteRequirement(index) {
    if (confirm('Are you sure you want to delete this requirement?')) {
      if (Array.isArray(requirements)) {
        setRequirements(prev => {
          const updatedRequirements = [...prev];
          updatedRequirements.splice(index, 1);
          return updatedRequirements;
        });
      } else {
        // Handle object format
        setRequirements(prev => {
          const updatedRequirements = {...prev};
          const keyToDelete = Object.keys(prev)[index];
          if (keyToDelete) {
            delete updatedRequirements[keyToDelete];
          }
          return updatedRequirements;
        });
      }
    }
  }
  
  const origins = ['Peninsular Malaysia', 'Sabah', 'Sarawak'];

  return (
    <div className="space-y-4 max-h-96 overflow-y-auto pr-2">
      <div className="flex justify-end mb-4">
        <button
          onClick={addNewRequirement}
          className="px-3 py-1 !bg-emerald-600 text-white rounded text-sm hover:bg-green-600"
        >
          + Add New Requirement
        </button>
      </div>
      
      <table className="min-w-full divide-y divide-slate-200 border border-slate-200 rounded-lg overflow-hidden">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">ID</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Grade</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Volume (kbbl)</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Origin</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Allowed Loading (Start-End)</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Required By (day)</th>
            <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-slate-100">
          {requirementsData.map((requirement, index) => {
            // Extract allowed_ldr values safely
            const ldrStartDay = requirement.allowed_ldr ? parseInt(Object.keys(requirement.allowed_ldr)[0]) || 0 : 0;
            const ldrEndDay = requirement.allowed_ldr ? parseInt(Object.values(requirement.allowed_ldr)[0]) || 0 : 0;
            console.log(`Rendering requirement ${index}:`, requirement);
            
            return (
              <tr key={index}>
                <td className="px-6 py-4 whitespace-nowrap">
                  <span className="text-sm text-slate-700">
                    {requirement.id || `Req_${index+1}`}
                  </span>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <select
                    value={requirement.grade || ''}
                    onChange={(e) => handleRequirementChange(index, 'grade', e.target.value)}
                    className="px-2 py-1 border border-slate-300 rounded w-40"
                    disabled={isLoading}
                  >
                    <option value="">
                      {isLoading ? "Loading crude grades..." : "Select a grade..."}
                    </option>
                    {crudeOptions.length > 0 ? 
                      crudeOptions.map(grade => (
                        <option key={grade} value={grade}>{grade}</option>
                      ))
                      :
                      !isLoading && <option value="" disabled>No grades available</option>
                    }
                  </select>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <input
                    type="number"
                    step="0.1"
                    min="0"
                    value={requirement.volume || 0}
                    onChange={(e) => handleRequirementChange(index, 'volume', e.target.value)}
                    className="px-2 py-1 border border-slate-300 rounded w-32"
                  />
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <select
                    value={requirement.origin || ''}
                    onChange={(e) => handleRequirementChange(index, 'origin', e.target.value)}
                    className="px-2 py-1 border border-slate-300 rounded w-40"
                  >
                    {origins.map(origin => (
                      <option key={origin} value={origin}>{origin}</option>
                    ))}
                  </select>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <div className="flex items-center">
                    <input
                      type="number"
                      min="0"
                      value={ldrStartDay}
                      onChange={(e) => handleLdrChange(index, parseInt(e.target.value) || 0, ldrEndDay)}
                      className="w-16 px-2 py-1.5 border border-slate-300 rounded-l"
                    />
                    <span className="px-2 text-slate-400">-</span>
                    <input
                      type="number"
                      min="0"
                      value={ldrEndDay}
                      onChange={(e) => handleLdrChange(index, ldrStartDay, parseInt(e.target.value) || 0)}
                      className="w-16 px-2 py-1.5 border border-slate-300 rounded-r"
                    />
                  </div>
                </td>
                <td className="px-6 py-4 whitespace-nowrap">
                  <input
                    type="number"
                    min="0"
                    value={requirement.required_arrival_by || 30}
                    onChange={(e) => handleRequirementChange(index, 'required_arrival_by', parseInt(e.target.value) || 30)}
                    className="px-2 py-1 border border-slate-300 rounded w-24"
                  />
                </td>
                <td className="px-6 py-4 whitespace-nowrap text-right">
                  <button
                    onClick={() => deleteRequirement(index)}
                    className="text-red-500 hover:text-red-700"
                    title="Delete requirement"
                  >
                    Delete
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      
      <div className="bg-blue-50 border border-blue-200 text-blue-800 p-4 rounded text-sm mt-4">
        <div className="flex items-start">
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2 text-blue-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <div>
            <p className="font-medium mb-1">About Feedstock Requirements</p>
            <p>Feedstock requirements represent crude volumes that must be delivered by the specified day to meet refinery processing demands. The "Allowed Loading" range indicates when the crude can be loaded at the origin.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
// Export the DataEditor component
export default DataEditor