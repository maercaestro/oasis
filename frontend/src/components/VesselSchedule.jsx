import { useState, useRef, useEffect } from 'react'
import { DndContext, useDraggable } from '@dnd-kit/core'
import { restrictToHorizontalAxis } from '@dnd-kit/modifiers'
import { VesselDashboardCards } from './DashboardCard' // Import the dashboard cards

function VesselSchedule({ vessels: initialVessels, onVesselUpdate }) {
  const [vessels, setVessels] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState(null)
  const [editingVessel, setEditingVessel] = useState(null)
  const [editFormData, setEditFormData] = useState({})
  const timelineRef = useRef(null)
  const [timelineConfig, setTimelineConfig] = useState({
    startDay: 1,
    daysToShow: 60,
    dayWidth: 40, // pixels per day
  })
  const [isCreatingVessel, setIsCreatingVessel] = useState(false)
  const [expandedVesselDetails, setExpandedVesselDetails] = useState({});

  // Location colors for route visualization
  const locationColors = {
    'Refinery': '#4ade80', // Green
    'Sabah': '#60a5fa',    // Blue
    'Sarawak': '#c084fc',  // Purple
    'Peninsular Malaysia': '#f97316' // Orange
  };

  // Get color for a location
  const getLocationColor = (location) => locationColors[location] || '#94a3b8'; // Default gray

  // Transform incoming vessel data to the expected format
  useEffect(() => {
    if (initialVessels) {
      const transformedVessels = transformVesselsData(initialVessels)
      setVessels(transformedVessels)
    } else {
      setVessels([])
    }
    setIsLoading(false)
  }, [initialVessels])

  // Transform vessels data
  const transformVesselsData = (vesselsData) => {
    // Check if it's a single vessel object
    if (vesselsData.vessel_id) {
      const vessel = vesselsData
      // Sum up all cargo volumes
      const totalVolume = vessel.cargo?.reduce((sum, cargo) => sum + (cargo.volume || 0), 0) || 0;
      // Determine crude type display
      const crudeType = vessel.cargo?.length > 1 ? "Multiple" : vessel.cargo?.[0]?.grade || "Unknown";
      
      return [{
        id: vessel.vessel_id,
        name: vessel.vessel_id,
        arrival_day: parseInt(vessel.arrival_day),
        departure_day: parseInt(vessel.arrival_day) + 3, // Default
        crude_type: crudeType,
        volume: totalVolume, // Now using the total volume of all cargo
        route: vessel.route || [],
        original: vessel
      }]
    } else if (typeof vesselsData === 'object') {
      // Handle dictionary format {Vessel_001: {...}, Vessel_002: {...}}
      return Object.entries(vesselsData).map(([key, vessel]) => {
        // Sum up all cargo volumes
        const totalVolume = vessel.cargo?.reduce((sum, cargo) => sum + (cargo.volume || 0), 0) || 0;
        // Determine crude type display
        const crudeType = vessel.cargo?.length > 1 ? "Multiple" : vessel.cargo?.[0]?.grade || "Unknown";
        
        return {
          id: key,
          name: vessel.vessel_id || key,
          arrival_day: parseInt(vessel.arrival_day),
          departure_day: parseInt(vessel.arrival_day) + 3, // Default
          crude_type: crudeType,
          volume: totalVolume, // Now using the total volume of all cargo
          route: vessel.route || [],
          original: vessel
        };
      })
    }
    return []
  }
  
  // Calculate timeline width
  const timelineWidth = timelineConfig.daysToShow * timelineConfig.dayWidth
  
  // Prepare days array for timeline header
  const days = Array.from({ length: timelineConfig.daysToShow }, (_, i) => {
    return timelineConfig.startDay + i
  })
  
  // Convert day to position on timeline
  const dayToPosition = (day) => {
    return (day - timelineConfig.startDay) * timelineConfig.dayWidth
  }
  
  // Handle vessel drag end event
  const handleDragEnd = (event) => {
    const { active, delta } = event
    const vesselId = active.id
    
    // Find the vessel being dragged
    const vessel = vessels.find(v => v.id === vesselId)
    if (!vessel) return
    
    // Calculate days moved based on pixel movement
    const daysMoved = Math.round(delta.x / timelineConfig.dayWidth)
    
    // Don't update if no movement
    if (daysMoved === 0) return
    
    // Calculate new days
    const newArrivalDay = vessel.arrival_day + daysMoved
    const newDepartureDay = vessel.departure_day + daysMoved
    
    // Update local state
    const updatedVessel = {
      ...vessel,
      arrival_day: newArrivalDay,
      departure_day: newDepartureDay
    }
    
    setVessels(prevVessels => 
      prevVessels.map(v => v.id === vesselId ? updatedVessel : v)
    )
    
    // Create API compatible vessel object
    const apiVessel = {
      ...vessel.original,
      arrival_day: newArrivalDay
    }
    
    onVesselUpdate(vesselId, apiVessel)
  }
  
  // Handle vessel selection for editing
  const handleSelectVessel = (vessel) => {
    setEditingVessel(vessel);
    // Update the form data structure to handle multiple cargo items
    setEditFormData({
      name: vessel.name,
      arrival_day: vessel.arrival_day,
      departure_day: vessel.departure_day,
      // Convert cargo to array format if needed
      cargo: vessel.original && vessel.original.cargo 
        ? [...vessel.original.cargo]  // Use existing cargo array
        : [{ grade: vessel.crude_type || '', volume: vessel.volume || 0 }]  // Create from single cargo
    });
  }

  // Add a new function to handle adding a cargo item
  const handleAddCargo = () => {
    if (editFormData.cargo && editFormData.cargo.length < 3) {
      setEditFormData(prev => ({
        ...prev,
        cargo: [...prev.cargo, { grade: '', volume: 0 }]
      }));
    }
  }

  // Add a function to handle removing a cargo item
  const handleRemoveCargo = (index) => {
    setEditFormData(prev => ({
      ...prev,
      cargo: prev.cargo.filter((_, i) => i !== index)
    }));
  }

  // Update the cargo form change handler
  const handleCargoChange = (index, field, value) => {
    setEditFormData(prev => {
      const newCargo = [...prev.cargo];
      newCargo[index] = { ...newCargo[index], [field]: field === 'volume' ? parseFloat(value) : value };
      return { ...prev, cargo: newCargo };
    });
  }

  // Add function to create a new vessel
  const handleCreateNewVessel = () => {
    setIsCreatingVessel(true);
    // Create default vessel data
    const newVessel = {
      id: `new_vessel_${Date.now()}`, // Temporary ID
      name: 'New Vessel',
      arrival_day: timelineConfig.startDay + 7, // Default to 7 days from timeline start
      departure_day: timelineConfig.startDay + 10, // Default 3-day stay
      original: {
        vessel_id: `Vessel_${Math.floor(Math.random() * 1000)}`,
        arrival_day: timelineConfig.startDay + 7,
        capacity: 1200, // Default capacity
        cost: 100000, // Default cost
        cargo: [{ grade: 'Arabian Light', volume: 0, origin: 'Sabah' }],
        days_held: 0
      }
    };
    
    setEditingVessel(newVessel);
    setEditFormData({
      name: newVessel.name,
      arrival_day: newVessel.arrival_day,
      departure_day: newVessel.departure_day,
      cargo: [...newVessel.original.cargo]
    });
  }

  // Save changes from edit form
  const handleSaveChanges = () => {
    if (!editingVessel) return;
    
    // Create updated vessel
    const updatedVessel = {
      ...editingVessel,
      name: editFormData.name,
      arrival_day: parseInt(editFormData.arrival_day),
      departure_day: parseInt(editFormData.departure_day),
      crude_type: editFormData.cargo?.[0]?.grade || '',
      volume: editFormData.cargo?.[0]?.volume || 0
    };
    
    // Create API compatible vessel object
    const apiVessel = {
      ...editingVessel.original,
      vessel_id: editFormData.name,
      arrival_day: parseInt(editFormData.arrival_day),
      days_held: parseInt(editFormData.departure_day) - parseInt(editFormData.arrival_day),
      cargo: editFormData.cargo.map(item => ({
        ...item,
        origin: item.origin || 'Sabah',
        loading_start_day: 0,
        loading_end_day: 0
      }))
    };
    
    if (isCreatingVessel) {
      // Add the new vessel to the vessels array
      setVessels(prev => [...prev, updatedVessel]);
      
      // Call the parent update handler with the new vessel ID and data
      onVesselUpdate(updatedVessel.id, apiVessel);
      setIsCreatingVessel(false);
    } else {
      // Update existing vessel
      setVessels(prevVessels => 
        prevVessels.map(v => v.id === editingVessel.id ? updatedVessel : v)
      );
      
      // Call the parent update handler
      onVesselUpdate(editingVessel.id, apiVessel);
    }
    
    // Reset form
    setEditingVessel(null);
  }
  
  // Close edit sidebar
  const handleCloseEdit = () => {
    setEditingVessel(null)
  }

  // Update the handleFormChange function

  const handleFormChange = (e) => {
    const { name, value } = e.target
    setEditFormData(prev => ({
      ...prev,
      [name]: name === 'arrival_day' || name === 'departure_day' 
        ? parseInt(value) 
        : value
    }))
  }

  // Add this function to render the route visualization
  const renderVesselRoute = (vessel) => {
    if (!vessel.route || vessel.route.length === 0) {
      return null;
    }
  
    const hasMultipleStops = vessel.route.length > 1;
    
    return (
      <div className="mt-2 relative">
        {/* Route timeline visualization */}
        <div className="h-3 relative w-full bg-white/20 rounded-full overflow-hidden">
          {vessel.route.map((segment, index) => {
            // Calculate positions for the entire journey
            const startDay = segment.day - segment.travel_days;
            const startPosition = dayToPosition(startDay) - dayToPosition(vessel.arrival_day);
            const endPosition = dayToPosition(segment.day) - dayToPosition(vessel.arrival_day);
            const width = Math.max(endPosition - startPosition, 4);
            
            return (
              <div 
                key={index}
                className="absolute h-full"
                style={{ 
                  left: `${startPosition}px`, 
                  width: `${width}px`,
                  background: `linear-gradient(to right, ${getLocationColor(segment.from)}, ${getLocationColor(segment.to)})`,
                  // Add traveling pattern
                  backgroundImage: index > 0 ? `repeating-linear-gradient(45deg, transparent, transparent 5px, rgba(255,255,255,0.3) 5px, rgba(255,255,255,0.3) 10px)` : '',
                }}
                title={`${segment.from} to ${segment.to} (Day ${startDay} - Day ${segment.day})`}
              />
            );
          })}
          
          {/* Stop markers */}
          {vessel.route.map((segment, index) => {
            // Show both departure and arrival points
            const departureDay = segment.day - segment.travel_days;
            const departurePosition = dayToPosition(departureDay) - dayToPosition(vessel.arrival_day);
            const arrivalDay = segment.day;
            const arrivalPosition = dayToPosition(arrivalDay) - dayToPosition(vessel.arrival_day);
            
            return (
              <>
                {/* Departure marker */}
                <div 
                  key={`departure-${index}`}
                  className="absolute w-3 h-3 rounded-full border-2 border-white transform -translate-x-1/2 -translate-y-1/3 z-10"
                  style={{ 
                    left: `${departurePosition}px`, 
                    top: '50%',
                    backgroundColor: getLocationColor(segment.from)
                  }}
                  title={`Depart from ${segment.from} on Day ${departureDay}`}
                />
                
                {/* Arrival marker */}
                <div 
                  key={`arrival-${index}`}
                  className="absolute w-3 h-3 rounded-full border-2 border-white transform -translate-x-1/2 -translate-y-1/3 z-10"
                  style={{ 
                    left: `${arrivalPosition}px`, 
                    top: '50%',
                    backgroundColor: getLocationColor(segment.to)
                  }}
                  title={`Arrive at ${segment.to} on Day ${arrivalDay}`}
                />
              </>
            );
          })}
        </div>
        
        {/* Travel indicators with day labels */}
        <div className="mt-1 text-xs text-white">
          {vessel.route.map((segment, index) => {
            const startDay = segment.day - segment.travel_days;
            const startPosition = dayToPosition(startDay) - dayToPosition(vessel.arrival_day);
            const midPosition = startPosition + (dayToPosition(segment.day) - dayToPosition(startDay)) / 2;
            
            return (
              <div 
                key={`travel-${index}`} 
                className="absolute flex flex-col items-center"
                style={{ left: `${midPosition}px`, transform: 'translateX(-50%)' }}
              >
                <div className="flex items-center">
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3 h-3 text-[#254E58]">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                  </svg>
                  <span className="text-[10px] text-[#254E58]">{segment.travel_days}d</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  };

  // Add this function to toggle vessel detail expansion
  const toggleVesselDetails = (vesselId) => {
    setExpandedVesselDetails(prev => ({
      ...prev,
      [vesselId]: !prev[vesselId]
    }));
  };

  // Draggable vessel component
  function DraggableVessel({ vessel, children }) {
    const { attributes, listeners, setNodeRef, transform } = useDraggable({
      id: vessel.id,
    });
    
    const style = transform ? {
      transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
    } : undefined;
    
    return (
      <div ref={setNodeRef} style={style} {...listeners} {...attributes}>
        {children}
      </div>
    );
  }

  // Add this function after your getVesselLocationByDay function

const renderDailyLocationBar = (vessel) => {
  if (!vessel.route || vessel.route.length === 0) {
    return null;
  }
  
  const totalDays = vessel.departure_day - vessel.arrival_day;
  
  // Generate array of days from arrival to departure
  const days = Array.from({ length: totalDays }, (_, i) => vessel.arrival_day + i);
  
  return (
    <div className="mt-2 mb-1">
      <div className="text-xs text-white mb-1">Daily Location:</div>
      <div className="flex h-4 w-full rounded-md overflow-hidden">
        {days.map(day => {
          // Find vessel location for this day
          let location = null;
          let isInTransit = false;
          
          for (const segment of vessel.route) {
            const departureDay = segment.day - segment.travel_days;
            const arrivalDay = segment.day;
            
            if (day >= departureDay && day <= arrivalDay) {
              if (day === departureDay) {
                location = segment.from;
              } else if (day === arrivalDay) {
                location = segment.to;
              } else {
                location = segment.to;
                isInTransit = true;
              }
              break;
            }
          }
          
          const backgroundColor = location ? getLocationColor(location) : '#e5e7eb';
          
          return (
            <div
              key={day}
              className="flex-1 flex items-center justify-center text-[9px] font-medium relative"
              style={{ 
                backgroundColor,
                backgroundImage: isInTransit ? 
                  'repeating-linear-gradient(-45deg, rgba(255,255,255,0.25), rgba(255,255,255,0.25) 4px, transparent 4px, transparent 8px)' : 
                  'none' 
              }}
              title={isInTransit ? `Day ${day}: Traveling to ${location}` : `Day ${day}: At ${location}`}
            >
              {/* Day number label - only show every few days to avoid crowding */}
              {day % 3 === 0 && (
                <span className={`absolute ${isInTransit ? 'text-white' : 'text-white'}`}>
                  {day}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-[#88BDBC] border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]"></div>
          <p className="mt-4 text-white font-medium">Loading vessel data...</p>
        </div>
      </div>
    )
  }
  
  // Empty state
  if (vessels.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center p-6">
          <div className="bg-[#88BDBC]/20 rounded-full w-16 h-16 flex items-center justify-center mx-auto mb-4 border border-[#88BDBC]/30">
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-8 h-8 text-[#88BDBC]">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-[#254E58] mb-2">No Vessels Found</h3>
          <p className="text-white">There are no vessels scheduled at this time.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="vessel-schedule h-full flex flex-col">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold text-[#254E58]">Vessel Schedule</h2>
        <div className="flex gap-2">
          <button 
            onClick={() => {
              setTimelineConfig(prev => ({
                ...prev,
                startDay: Math.max(1, prev.startDay - 7)
              }))
            }}
            className="px-3 py-1 rounded bg-[#88BDBC]/20 text-[#254E58] hover:bg-[#88BDBC]/30 backdrop-blur-sm border border-[#88BDBC]/30"
          >
            ← Previous Week
          </button>
          <button 
            onClick={() => {
              setTimelineConfig(prev => ({
                ...prev,
                startDay: prev.startDay + 7
              }))
            }}
            className="px-3 py-1 rounded bg-[#88BDBC]/20 text-[#254E58] hover:bg-[#88BDBC]/30 backdrop-blur-sm border border-[#88BDBC]/30"
          >
            Next Week →
          </button>
        </div>
      </div>
      
      {/* Add Dashboard Cards */}
      <VesselDashboardCards vessels={vessels} />
      
      {/* Main content with vertical layout */}
      <div className="flex flex-col h-full">
        {/* Timeline container with both horizontal and vertical scrolling */}
        <div className="timeline-container flex-grow overflow-x-auto overflow-y-auto border border-[#88BDBC]/30 rounded-lg mb-4 bg-white/90 backdrop-blur-sm">
          <div 
            ref={timelineRef}
            className="relative"
            style={{ width: `${timelineWidth}px`, minHeight: '300px' }}
          >
            {/* Timeline header with days - make it sticky */}
            <div className="timeline-header sticky top-0 bg-white/95 backdrop-blur-sm z-10 border-b border-[#88BDBC]/30">
              <div className="flex">
                {days.map((day, index) => (
                  <div 
                    key={index}
                    className={`text-center border-r border-[#88BDBC]/20 py-2 flex-shrink-0 ${
                      (day % 7 === 0 || day % 7 === 1) ? 'bg-[#88BDBC]/10' : ''
                    }`}
                    style={{ width: `${timelineConfig.dayWidth}px` }}
                  >
                    <div className="font-medium text-[#254E58]">Day {day}</div>
                  </div>
                ))}
              </div>
            </div>
            
            {/* Vessels as draggable items */}
            <DndContext 
              onDragEnd={handleDragEnd}
              modifiers={[restrictToHorizontalAxis]}
            >
              <div className="vessels-container pt-4">
                {vessels.map((vessel) => {
                  const startPosition = dayToPosition(vessel.arrival_day)
                  const endPosition = dayToPosition(vessel.departure_day)
                  const width = Math.max(endPosition - startPosition, 100)
                  
                  // Add this function to get the vessel's current location on each day
                  const getVesselLocationByDay = (day) => {
                    if (!vessel.route || vessel.route.length === 0) return null;
                    
                    for (const segment of vessel.route) {
                      const departureDay = segment.day - segment.travel_days;
                      const arrivalDay = segment.day;
                      
                      if (day >= departureDay && day <= arrivalDay) {
                        if (day === departureDay) return segment.from;
                        if (day === arrivalDay) return segment.to;
                        return `Traveling from ${segment.from} to ${segment.to}`;
                      }
                    }
                    return null;
                  };
                  
                  return (
                    <div 
                      key={vessel.id} 
                      className="vessel-row relative mb-4 h-16" // Reduced height for cleaner look
                    >
                      <div className="absolute left-0 h-full flex items-center px-2 text-sm font-medium text-[#254E58] w-40">
                        <div className="flex flex-col">
                          <span className="font-medium">{vessel.name}</span>
                          <span className="text-xs text-white">{vessel.volume} kbbl</span>
                        </div>
                      </div>
                      
                      <div className="absolute" style={{ left: `40px` }}>
                        <DraggableVessel vessel={vessel}>
                          <div 
                            className={`vessel-item absolute rounded-md transition-all shadow-sm hover:shadow ${
                              editingVessel && editingVessel.id === vessel.id 
                                ? 'border-2 border-[#88BDBC] shadow-md' 
                                : 'border border-[#88BDBC]/30 bg-[#88BDBC]/20 hover:bg-[#88BDBC]/30 backdrop-blur-sm'
                            }`}
                            style={{ 
                              width: `${width}px`, 
                              height: '90%',
                              left: `${startPosition}px`,
                            }}
                            onDoubleClick={() => handleSelectVessel(vessel)}
                          >
                            {/* Simple vessel display - just name and volume */}
                            <div className="h-full flex items-center px-3 justify-between">
                              <div className="flex items-center">
                                <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4 text-[#254E58] mr-2">
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5" />
                                </svg>
                                <span className="font-medium text-sm text-[#254E58]">{vessel.name}</span>
                              </div>
                              
                              <div className="flex items-center">
                                <span className="text-xs text-[#88BDBC] bg-white/90 px-2 py-0.5 rounded-full border border-[#88BDBC]/30">
                                  {vessel.volume} kbbl
                                </span>
                                
                                {/* Small indicator if route exists */}
                                {vessel.route && vessel.route.length > 0 && (
                                  <button 
                                    onClick={(e) => { e.stopPropagation(); toggleVesselDetails(vessel.id); }}
                                    className="ml-2 text-[#88BDBC] hover:text-[#254E58] p-1 rounded-full hover:bg-white/20"
                                    title="Show route details"
                                  >
                                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.5 4.5L21 12m0 0l-7.5 7.5M21 12H3" />
                                    </svg>
                                  </button>
                                )}
                              </div>
                            </div>
                            
                            {/* Expanded details popup - keep this functionality */}
                            {expandedVesselDetails[vessel.id] && (
                              <div className="absolute top-full left-0 z-20 bg-white/95 backdrop-blur-md rounded-md shadow-lg border border-[#88BDBC]/30 p-3 w-80 mt-2">
                                <h4 className="font-semibold text-[#254E58] mb-2">Vessel Route Details</h4>
                                <div className="space-y-2">
                                  {vessel.route.map((segment, index) => (
                                    <div key={index} className="text-sm">
                                      <div className="flex items-center">
                                        <div className="w-3 h-3 rounded-full mr-2" style={{ backgroundColor: getLocationColor(segment.from) }}></div>
                                        <span className="font-medium text-[#254E58]">{segment.from}</span>
                                        <span className="text-white ml-1">(Day {segment.day - segment.travel_days})</span>
                                      </div>
                                      <div className="ml-5 my-1 flex items-center">
                                        <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3 h-3 text-white mr-1">
                                          <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 13.5L12 21m0 0l-7.5-7.5M12 21V3" />
                                        </svg>
                                        <span className="text-xs text-white">
                                          Traveling for {segment.travel_days} days
                                        </span>
                                      </div>
                                      <div className="flex items-center">
                                        <div className="w-3 h-3 rounded-full mr-2" style={{ backgroundColor: getLocationColor(segment.to) }}></div>
                                        <span className="font-medium text-[#254E58]">{segment.to}</span>
                                        <span className="text-white ml-1">(Day {segment.day})</span>
                                      </div>
                                      {index < vessel.route.length - 1 && (
                                        <div className="h-4 border-l border-dashed border-[#88BDBC]/30 ml-1.5"></div>
                                      )}
                                    </div>
                                  ))}
                                </div>
                                <button
                                  onClick={() => toggleVesselDetails(vessel.id)}
                                  className="absolute top-2 right-2 text-white hover:text-[#254E58]"
                                >
                                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                  </svg>
                                </button>
                              </div>
                            )}
                          </div>
                        </DraggableVessel>
                      </div>
                    </div>
                  )
                })}
              </div>
            </DndContext>
          </div>
        </div>
        
        {/* Edit form at the bottom - always visible */}
        <div className="border border-[#88BDBC]/30 rounded-lg bg-white/95 backdrop-blur-sm p-4 h-[280px] overflow-y-auto">
          <div className="flex justify-between items-center mb-4">
            <div className="flex items-center gap-3">
              <h3 className="text-lg font-semibold text-[#254E58]">
                {isCreatingVessel ? 'Create New Vessel' : editingVessel ? `Edit ${editingVessel.name}` : 'Vessel Editor'}
              </h3>
              {!editingVessel && (
                <button
                  onClick={handleCreateNewVessel}
                  className="px-3 py-1.5 bg-gradient-to-r from-[#88BDBC] to-[#254E58] hover:from-[#254E58] hover:to-[#88BDBC] text-white rounded flex items-center gap-1.5 text-sm transition-all duration-200 shadow-lg"
                >
                  <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                  </svg>
                  Add New Vessel
                </button>
              )}
            </div>
            {editingVessel && (
              <button 
                onClick={handleCloseEdit}
                className="text-white hover:text-[#254E58]"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
          
          {!editingVessel ? (
            <div className="flex flex-col items-center justify-center h-[180px] text-white">
              <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-10 h-10 mb-2 text-[#88BDBC]">
                <path strokeLinecap="round" strokeLinejoin="round" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z" />
              </svg>
              <p className="text-center">Double-click on a vessel to edit its details or create a new vessel</p>
            </div>
          ) : (
            <form onSubmit={(e) => { e.preventDefault(); handleSaveChanges(); }} className="space-y-4">
              {/* Vessel details */}
              <div className="grid grid-cols-3 gap-4">
                <div className="col-span-1">
                  <label className="block text-[#254E58] text-sm font-bold mb-1">
                    Vessel Name
                  </label>
                  <input
                    type="text"
                    name="name"
                    value={editFormData.name || ''}
                    onChange={handleFormChange}
                    className="shadow appearance-none border border-[#88BDBC]/30 rounded w-full py-2 px-3 text-[#254E58] leading-tight focus:outline-none focus:ring-2 focus:ring-[#88BDBC]/50 bg-white/90"
                  />
                </div>
                
                <div className="col-span-1">
                  <label className="block text-[#254E58] text-sm font-bold mb-1">
                    Arrival Day
                  </label>
                  <input
                    type="number"
                    name="arrival_day"
                    value={editFormData.arrival_day || ''}
                    onChange={handleFormChange}
                    className="shadow appearance-none border border-[#88BDBC]/30 rounded w-full py-2 px-3 text-[#254E58] leading-tight focus:outline-none focus:ring-2 focus:ring-[#88BDBC]/50 bg-white/90"
                  />
                </div>
                
                <div className="col-span-1">
                  <label className="block text-[#254E58] text-sm font-bold mb-1">
                    Departure Day
                  </label>
                  <input
                    type="number"
                    name="departure_day"
                    value={editFormData.departure_day || ''}
                    onChange={handleFormChange}
                    className="shadow appearance-none border border-[#88BDBC]/30 rounded w-full py-2 px-3 text-[#254E58] leading-tight focus:outline-none focus:ring-2 focus:ring-[#88BDBC]/50 bg-white/90"
                  />
                </div>
              </div>
              
              {/* Cargo section */}
              <div className="mt-4">
                <div className="flex justify-between items-center mb-2">
                  <h4 className="font-semibold text-[#254E58]">Cargo</h4>
                  {editFormData.cargo && editFormData.cargo.length < 3 && (
                    <button
                      type="button"
                      onClick={handleAddCargo}
                      className="px-2 py-1 bg-[#88BDBC]/20 text-[#254E58] rounded text-sm hover:bg-[#88BDBC]/30 backdrop-blur-sm border border-[#88BDBC]/30 flex items-center gap-1"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-3 h-3">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4.5v15m7.5-7.5h-15" />
                      </svg>
                      Add Crude
                    </button>
                  )}
                </div>
                
                {/* Cargo items */}
                <div className="space-y-3">
                  {editFormData.cargo && editFormData.cargo.map((cargo, index) => (
                    <div key={index} className="grid grid-cols-5 gap-3 items-end bg-[#88BDBC]/10 p-2 rounded border border-[#88BDBC]/20 backdrop-blur-sm">
                      <div className="col-span-2">
                        <label className="block text-[#254E58] text-xs font-medium mb-1">
                          Crude Type
                        </label>
                        <input
                          type="text"
                          value={cargo.grade || ''}
                          onChange={(e) => handleCargoChange(index, 'grade', e.target.value)}
                          className="shadow appearance-none border border-[#88BDBC]/30 rounded w-full py-1.5 px-2 text-[#254E58] text-sm leading-tight focus:outline-none focus:ring-2 focus:ring-[#88BDBC]/50 bg-white/90"
                        />
                      </div>
                      
                      <div className="col-span-2">
                        <label className="block text-[#254E58] text-xs font-medium mb-1">
                          Volume (kbbl) <span className="text-white font-normal">max 700</span>
                        </label>
                        <input
                          type="number"
                          min="0"
                          max="700"
                          value={cargo.volume || 0}
                          onChange={(e) => handleCargoChange(index, 'volume', e.target.value)}
                          className="shadow appearance-none border border-[#88BDBC]/30 rounded w-full py-1.5 px-2 text-[#254E58] text-sm leading-tight focus:outline-none focus:ring-2 focus:ring-[#88BDBC]/50 bg-white/90"
                        />
                      </div>
                      
                      <div className="col-span-1 flex justify-end">
                        {editFormData.cargo.length > 1 && (
                          <button
                            type="button"
                            onClick={() => handleRemoveCargo(index)}
                            className="h-8 w-8 flex items-center justify-center text-red-400 hover:bg-red-50 rounded"
                          >
                            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" className="w-4 h-4">
                              <path strokeLinecap="round" strokeLinejoin="round" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0" />
                            </svg>
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
              
              {/* Route information (read-only) */}
              {editingVessel && editingVessel.route && editingVessel.route.length > 0 && (
                <div className="mt-4">
                  <h4 className="font-semibold text-[#254E58] mb-2">Route Information:</h4>
                  <div className="bg-[#88BDBC]/10 p-3 rounded text-sm border border-[#88BDBC]/20 backdrop-blur-sm">
                    <div className="space-y-2">
                      {editingVessel.route.map((segment, index) => (
                        <div key={index} className="flex items-center">
                          <div 
                            className="w-3 h-3 rounded-full mr-2 flex-shrink-0" 
                            style={{ backgroundColor: getLocationColor(segment.from) }}
                          ></div>
                          <span className="text-[#254E58]">
                            {segment.from} → {segment.to} 
                            <span className="text-white ml-2">
                              (Day {segment.day - segment.travel_days} - Day {segment.day}, {segment.travel_days} days)
                            </span>
                          </span>
                        </div>
                      ))}
                    </div>
                    <div className="mt-2 text-xs text-white">
                      Route information is generated by the vessel optimizer and cannot be edited manually.
                    </div>
                  </div>
                </div>
              )}
              
              {/* Form buttons */}
              <div className="flex justify-end gap-2 pt-2 border-t border-[#88BDBC]/30 mt-4">
                <button
                  type="button"
                  onClick={handleCloseEdit}
                  className="px-4 py-2 bg-white/20 text-[#254E58] rounded hover:bg-white/30 border border-white/30"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="px-4 py-2 bg-gradient-to-r from-[#88BDBC] to-[#254E58] text-white rounded hover:from-[#254E58] hover:to-[#88BDBC] transition-all duration-200 shadow-lg"
                >
                  {isCreatingVessel ? 'Create Vessel' : 'Save Changes'}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
      {/* Location color legend */}
      <div className="mt-4 pt-3 border-t border-[#88BDBC]/30">
        <h4 className="text-sm font-medium text-[#254E58] mb-2">Location Legend:</h4>
        <div className="flex flex-wrap gap-x-4 gap-y-2">
          {Object.entries(locationColors).map(([location, color]) => (
            <div key={location} className="flex items-center">
              <div className="w-3 h-3 rounded-full mr-1" style={{ backgroundColor: color }}></div>
              <span className="text-xs text-white">{location}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

export default VesselSchedule