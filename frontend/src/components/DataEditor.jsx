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
      
      // Save changes via API
      await axios.post('/api/data', {
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
        return <TankDataEditor tanks={editableData} setTanks={setEditableData} />;
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
      default:
        return <p>Select a data type to edit</p>;
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
          className="px-4 py-2 bg-blue-600 text-white font-medium rounded-lg hover:bg-blue-700 disabled:bg-blue-300 disabled:cursor-not-allowed transition"
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
  )
}

// Tank Editor Component
function TankDataEditor({ tanks, setTanks }) {
  // Add defensive checks for undefined or null data
  const tanksData = tanks || {};
  
  // Handle empty tanks object
  if (Object.keys(tanksData).length === 0) {
    return <p className="text-slate-500">No tank data available to edit.</p>
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
  
  const handleContentChange = (tankName, contentIndex, grade, value) => {
    // Create a copy of the tanks object
    const updatedTanks = { ...tanks }
    
    // Extract current content array for this tank
    const tankContent = [...updatedTanks[tankName].content]
    
    // If this is adding a new grade that wasn't in the content array before
    if (contentIndex >= tankContent.length) {
      tankContent.push({ [grade]: parseFloat(value) || 0 })
    } else {
      // Otherwise update existing content
      const existingContent = tankContent[contentIndex]
      const existingGrade = Object.keys(existingContent)[0]
      
      // If grade changed, create new object with new grade
      if (grade !== existingGrade) {
        tankContent[contentIndex] = { [grade]: parseFloat(value) || 0 }
      } else {
        // Just update the value for existing grade
        tankContent[contentIndex] = { [grade]: parseFloat(value) || 0 }
      }
    }
    
    // Filter out any entries with zero or negative volumes
    const filteredContent = tankContent.filter(item => {
      const value = Object.values(item)[0]
      return value > 0
    })
    
    // Update the tank with new content
    updatedTanks[tankName].content = filteredContent
    
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
  
  // Fix the allGrades extraction with proper null checks
  const allGrades = [...new Set(
    Object.values(tanksData)
      .filter(tank => tank && tank.content) // Make sure tank and content exist
      .flatMap(tank => 
        tank.content
          .filter(item => item !== null && item !== undefined) // Filter out null/undefined items
          .flatMap(item => Object.keys(item || {}))
      )
  )].filter(Boolean); // Filter out empty strings
  
  return (
    <div className="space-y-4 max-h-96 overflow-y-auto pr-2">
      {/* Use tanksData instead of tanks here */}
      {Object.entries(tanksData).map(([tankName, tank]) => {
        // Add safety check for tank.content
        const tankContent = tank.content || [];
        
        return (
          <div key={tankName} className="border border-slate-200 rounded-lg p-4">
            <div className="flex justify-between items-center mb-3">
              <h3 className="font-bold text-slate-800">{tankName}</h3>
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
                      {allGrades.map(g => (
                        <option key={g} value={g}>{g}</option>
                      ))}
                      <option value="__custom">+ Add new grade</option>
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
  const allOrigins = [...new Set(
    vesselsData
      .filter(vessel => vessel && vessel.cargo)
      .flatMap(vessel => 
        vessel.cargo
          .filter(item => item !== null && item !== undefined)
          .map(item => item.origin)
      )
  )].filter(Boolean);
  
  const allGrades = [...new Set(
    vesselsData
      .filter(vessel => vessel && vessel.cargo)
      .flatMap(vessel => 
        vessel.cargo
          .filter(item => item !== null && item !== undefined)
          .map(item => item.grade)
      )
  )].filter(Boolean);

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
        </div>
      ))}
    </div>
  );
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
          className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
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
    setNewCrude({ name: '', margin: 0, origin: 'Terminal1' });
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
    setNewCrude({ name: '', margin: 0, origin: 'Terminal1' });
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

  const terminals = ['Terminal1', 'Terminal2', 'Terminal3'];

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
            className="px-3 py-1 bg-green-500 text-white rounded text-sm hover:bg-green-600"
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
              className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
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
                  disabled={editingName === crudeId}
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

// Replace the current RecipeDataEditor with this one:

function RecipeDataEditor({ recipes, setRecipes, crudes }) {
  const recipesData = recipes || {};
  const crudesData = crudes || {};
  const [isAddingRecipe, setIsAddingRecipe] = useState(false);
  const [newRecipe, setNewRecipe] = useState({
    name: '',
    primary_grade: '',
    secondary_grade: null,
    max_rate: 250.0,
    primary_fraction: 0.7
  });
  const [error, setError] = useState('');
  
  if (Object.keys(recipesData).length === 0 && !isAddingRecipe) {
    return (
      <div className="text-center p-8">
        <p className="text-slate-500 mb-4">No recipe data available.</p>
        <button
          onClick={() => setIsAddingRecipe(true)}
          className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
        >
          + Add First Recipe
        </button>
      </div>
    );
  }

  // Get available crude names from crudes.json
  const crudeOptions = Object.keys(crudesData);

  const handleRecipeChange = (recipeId, property, value) => {
    // Handle numeric values
    if (property === 'max_rate') {
      value = parseFloat(value) || 0;
    }
    else if (property === 'primary_fraction') {
      value = parseFloat(value) || 0;
      // Constrain to 0-1 range
      value = Math.max(0, Math.min(1, value));
    }
    
    setRecipes(prev => ({
      ...prev,
      [recipeId]: {
        ...prev[recipeId],
        [property]: value
      }
    }));
  };
  
  const handleNewRecipeChange = (property, value) => {
    // Handle numeric values
    if (property === 'max_rate') {
      value = parseFloat(value) || 0;
    }
    else if (property === 'primary_fraction') {
      value = parseFloat(value) || 0;
      // Constrain to 0-1 range
      value = Math.max(0, Math.min(1, value));
    }
    
    setNewRecipe(prev => ({
      ...prev,
      [property]: value
    }));
  };
  
  const addNewRecipe = () => {
    setNewRecipe({
      name: '',
      primary_grade: crudeOptions.length > 0 ? crudeOptions[0] : '',
      secondary_grade: crudeOptions.length > 1 ? crudeOptions[1] : null,
      max_rate: 250.0,
      primary_fraction: 0.7
    });
    setIsAddingRecipe(true);
    setError('');
  };
  
  const cancelAddRecipe = () => {
    setIsAddingRecipe(false);
    setNewRecipe({
      name: '',
      primary_grade: '',
      secondary_grade: null,
      max_rate: 250.0,
      primary_fraction: 0.7
    });
    setError('');
  };
  
  const saveNewRecipe = () => {
    if (!newRecipe.name.trim()) {
      setError('Recipe name cannot be empty');
      return;
    }
    
    if (recipesData[newRecipe.name]) {
      setError(`A recipe named "${newRecipe.name}" already exists`);
      return;
    }
    
    if (!newRecipe.primary_grade) {
      setError('Primary grade is required');
      return;
    }
    
    setRecipes(prev => ({
      ...prev,
      [newRecipe.name]: {
        name: newRecipe.name,
        primary_grade: newRecipe.primary_grade,
        secondary_grade: newRecipe.secondary_grade === "" ? null : newRecipe.secondary_grade,
        max_rate: newRecipe.max_rate,
        primary_fraction: newRecipe.primary_fraction
      }
    }));
    
    setIsAddingRecipe(false);
    setNewRecipe({
      name: '',
      primary_grade: '',
      secondary_grade: null,
      max_rate: 250.0,
      primary_fraction: 0.7
    });
    setError('');
  };
  
  const deleteRecipe = (recipeId) => {
    if (confirm(`Are you sure you want to delete ${recipeId}?`)) {
      setRecipes(prev => {
        const copy = {...prev};
        delete copy[recipeId];
        return copy;
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
            className="px-3 py-1 bg-green-500 text-white rounded text-sm hover:bg-green-600"
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
              className="px-3 py-1 bg-blue-600 text-white rounded text-sm hover:bg-blue-700"
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

// Add new RouteDataEditor component
function RouteDataEditor({ routes, setRoutes }) {
  const routesData = Array.isArray(routes) ? routes : [];
  
  if (routesData.length === 0) {
    return (
      <div className="text-center p-8">
        <p className="text-slate-500 mb-4">No route data available.</p>
        <button
          onClick={addNewRoute}
          className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
        >
          + Add First Route
        </button>
      </div>
    );
  }

  function handleRouteChange(index, property, value) {
    setRoutes(prev => {
      const updatedRoutes = [...prev];
      updatedRoutes[index] = {
        ...updatedRoutes[index],
        [property]: property === 'cost' ? parseFloat(value) : value
      };
      return updatedRoutes;
    });
  }
  
  function addNewRoute() {
    setRoutes(prev => [
      ...prev,
      {
        origin: 'Terminal1',
        destination: '',
        cost: 0
      }
    ]);
  }
  
  function deleteRoute(index) {
    if (confirm('Are you sure you want to delete this route?')) {
      setRoutes(prev => {
        const updatedRoutes = [...prev];
        updatedRoutes.splice(index, 1);
        return updatedRoutes;
      });
    }
  }

  const terminals = ['Terminal1', 'Terminal2', 'Terminal3'];

  return (
    <div className="space-y-4 max-h-96 overflow-y-auto pr-2">
      <div className="flex justify-end mb-4">
        <button
          onClick={addNewRoute}
          className="px-3 py-1 bg-green-500 text-white rounded text-sm hover:bg-green-600"
        >
          + Add New Route
        </button>
      </div>
      
      <table className="min-w-full divide-y divide-slate-200 border border-slate-200 rounded-lg overflow-hidden">
        <thead className="bg-slate-50">
          <tr>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Origin</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Destination</th>
            <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Cost ($)</th>
            <th className="px-6 py-3 text-right text-xs font-medium text-slate-500 uppercase tracking-wider">Actions</th>
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-slate-100">
          {routesData.map((route, index) => (
            <tr key={index}>
              <td className="px-6 py-4 whitespace-nowrap">
                <select
                  value={route.origin || ''}
                  onChange={(e) => handleRouteChange(index, 'origin', e.target.value)}
                  className="px-2 py-1 border border-slate-300 rounded"
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
                  onChange={(e) => handleRouteChange(index, 'destination', e.target.value)}
                  className="px-2 py-1 border border-slate-300 rounded w-40"
                />
              </td>
              <td className="px-6 py-4 whitespace-nowrap">
                <input
                  type="number"
                  value={route.cost || 0}
                  onChange={(e) => handleRouteChange(index, 'cost', e.target.value)}
                  className="px-2 py-1 border border-slate-300 rounded w-32"
                />
              </td>
              <td className="px-6 py-4 whitespace-nowrap text-right">
                <button
                  onClick={() => deleteRoute(index)}
                  className="text-red-500 hover:text-red-700"
                  title="Delete route"
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

// Add new VesselTypeDataEditor component
function VesselTypeDataEditor({ vesselTypes, setVesselTypes }) {
  const vesselTypesData = Array.isArray(vesselTypes) ? vesselTypes : [];
  
  if (vesselTypesData.length === 0) {
    return (
      <div className="text-center p-8">
        <p className="text-slate-500 mb-4">No vessel type data available.</p>
        <button
          onClick={addNewVesselType}
          className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
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
          className="px-3 py-1 bg-green-500 text-white rounded text-sm hover:bg-green-600"
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

export default DataEditor