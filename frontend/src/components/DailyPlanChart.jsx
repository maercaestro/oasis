import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line, AreaChart, Area } from 'recharts'
import axios from 'axios'
import { DashboardCard, ScheduleDashboardCards } from './DashboardCard' // Import the dashboard cards

function DailyPlanChart({ schedule, onScheduleChange, originalSchedule = null }) {
  const [viewType, setViewType] = useState('processing')
  const [showDetails, setShowDetails] = useState(false)
  const [editMode, setEditMode] = useState(false)
  const [editedSchedule, setEditedSchedule] = useState([])
  const [selectedDay, setSelectedDay] = useState(null)
  const [selectedTank, setSelectedTank] = useState(null)
  const [saveStatus, setSaveStatus] = useState('')
  
  // Initialize edited schedule when component mounts or schedule changes
  useEffect(() => {
    if (schedule && schedule.length > 0) {
      setEditedSchedule(JSON.parse(JSON.stringify(schedule)))
    }
  }, [schedule])
  
  // Early return if no schedule data
  if (!schedule || schedule.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <p className="text-white">No schedule data available.</p>
      </div>
    )
  }
  
  // NEW FUNCTION: Calculate grade consumption based on recipe processing rates
  const calculateGradeConsumption = (day) => {
    const gradeConsumption = {}
    
    // Get processing rates and recipe details
    const processingRates = day.processing_rates || {}
    const blendingDetails = day.blending_details || []
    
    // Create a map of recipe name to recipe details
    const recipeMap = {}
    blendingDetails.forEach(recipe => {
      recipeMap[recipe.name] = recipe
    })
    
    // Calculate consumption for each grade based on recipes used
    Object.entries(processingRates).forEach(([recipeName, rate]) => {
      const recipe = recipeMap[recipeName]
      if (!recipe) return
      
      // Calculate primary grade consumption
      const primaryGrade = recipe.primary_grade
      const primaryAmount = rate * recipe.primary_fraction
      
      if (primaryGrade) {
        if (!gradeConsumption[primaryGrade]) {
          gradeConsumption[primaryGrade] = 0
        }
        gradeConsumption[primaryGrade] += primaryAmount
      }
      
      // Calculate secondary grade consumption (if exists)
      if (recipe.secondary_grade) {
        const secondaryGrade = recipe.secondary_grade
        const secondaryAmount = rate * (1 - recipe.primary_fraction)
        
        if (!gradeConsumption[secondaryGrade]) {
          gradeConsumption[secondaryGrade] = 0
        }
        gradeConsumption[secondaryGrade] += secondaryAmount
      }
    })
    
    return gradeConsumption
  }
  
  // Process data for charts
  const chartData = editedSchedule.map(day => {
    // Get total processing amount and per-recipe amounts
    const processingRates = {}
    let totalProcessing = 0
    
    Object.entries(day.processing_rates || {}).forEach(([recipe, rate]) => {
      processingRates[recipe] = rate
      totalProcessing += rate
    })
    
    // Get grade consumption (NEW)
    const gradeConsumption = calculateGradeConsumption(day)
    
    // Get inventory by grade
    const inventoryByGrade = {}
    let totalInventory = 0
    
    Object.entries(day.inventory_by_grade || {}).forEach(([grade, amount]) => {
      inventoryByGrade[grade] = amount
      totalInventory += amount
    })
    
    // Get tanks data
    const tankData = {}
    if (day.tanks) {
      Object.entries(day.tanks).forEach(([tankName, tank]) => {
        // Sum up content if there are multiple entries
        let tankTotal = 0
        const tankContentByGrade = {}
        
        if (tank.content && Array.isArray(tank.content)) {
          tank.content.forEach(contentItem => {
            const grade = Object.keys(contentItem)[0]
            const amount = contentItem[grade] || 0
            tankTotal += amount
            tankContentByGrade[`tank_${tankName}_${grade}`] = amount
          })
        }
        
        tankData[`tank_${tankName}_total`] = tankTotal
        Object.assign(tankData, tankContentByGrade)
      })
    }
    
    return {
      day: day.day,
      dayLabel: `Day ${day.day}`,
      totalProcessing,
      totalInventory,
      ...processingRates, // Keep the original recipe data for editing
      // Add grade consumption data with a prefix to differentiate
      ...Object.entries(gradeConsumption).reduce((acc, [grade, amount]) => {
        acc[`grade_${grade}`] = amount
        return acc
      }, {}),
      ...Object.entries(inventoryByGrade).reduce((acc, [grade, amount]) => {
        acc[`inventory_${grade}`] = amount
        return acc
      }, {}),
      ...tankData
    }
  })
  
  // Get unique recipe names for reference
  const recipes = [...new Set(
    schedule.flatMap(day => 
      Object.keys(day.processing_rates || {})
    )
  )]
  
  // Get unique grades for processing chart (NEW)
  const processedGrades = [...new Set(
    schedule.flatMap(day => {
      const gradeConsumption = calculateGradeConsumption(day)
      return Object.keys(gradeConsumption)
    })
  )]
  
  // Get unique crude grades for inventory
  const grades = [...new Set(
    schedule.flatMap(day => 
      Object.keys(day.inventory_by_grade || {})
    )
  )]
  
  // Get unique tank names
  const tanks = [...new Set(
    schedule.flatMap(day => 
      Object.keys(day.tanks || {})
    )
  )]
  
  // Generate colors for different data series - Creative vibrant palette with teal harmony
  // Option 1: Ocean-to-Sunset palette (recommended)
  //const recipeColors = ['#254E58', '#2DD4BF', '#06B6D4', '#F59E0B', '#EC4899', '#8B5CF6']
  //const gradeColors = ['#0891B2', '#10B981', '#F97316', '#EF4444', '#8B5CF6', '#06B6D4']
  //const tankColors = ['#14B8A6', '#3B82F6', '#F59E0B', '#EF4444', '#EC4899', '#8B5CF6']
  
  // Alternative palettes (uncomment to try):
  // Option 2: Jewel Tones
  //const recipeColors = ['#254E58', '#059669', '#DC2626', '#7C3AED', '#DB2777', '#EA580C']
  //const gradeColors = ['#0891B2', '#059669', '#DC2626', '#7C3AED', '#DB2777', '#EA580C']
  //const tankColors = ['#14B8A6', '#059669', '#DC2626', '#7C3AED', '#DB2777', '#EA580C']
  
  // Option 3: Modern Tech palette
  const recipeColors = ['#254E58', '#00D9FF', '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
  const gradeColors = ['#0891B2', '#00D9FF', '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
  const tankColors = ['#14B8A6', '#00D9FF', '#FF6B6B', '#4ECDC4', '#45B7D1', '#96CEB4']
  
  // Handle value edit in table
  const handleValueChange = (dayIndex, key, value) => {
    // Copy the schedule to avoid direct mutation
    const newSchedule = [...editedSchedule]
    const day = newSchedule[dayIndex]
    
    // Handle different data types
    if (key.startsWith('inventory_')) {
      // Edit inventory by grade
      const grade = key.replace('inventory_', '')
      
      // Ensure inventory_by_grade object exists
      if (!day.inventory_by_grade) {
        day.inventory_by_grade = {}
      }
      
      // Update the specific grade
      const numValue = value === '' ? 0 : parseFloat(value) || 0
      day.inventory_by_grade[grade] = numValue
      
      // Update total inventory
      day.inventory = Object.values(day.inventory_by_grade).reduce((sum, val) => sum + val, 0)
    } 
    else if (key.startsWith('tank_')) {
      // Handle tank edits
      const parts = key.split('_')
      const tankName = parts[1]
      
      if (parts.length === 3 && parts[2] === 'total') {
        // Can't directly edit tank total, it's calculated from contents
      } else if (parts.length >= 3) {
        // Edit tank content for specific grade
        const grade = parts.slice(2).join('_')
        
        if (!day.tanks[tankName]) {
          day.tanks[tankName] = { name: tankName, content: [] }
        }
        
        // Find if this grade already exists in the tank
        const contentIndex = day.tanks[tankName].content.findIndex(item => 
          Object.keys(item)[0] === grade
        )
        
        if (contentIndex >= 0) {
          const numValue = value === '' ? 0 : parseFloat(value) || 0
          day.tanks[tankName].content[contentIndex] = { [grade]: numValue }
        } else {
          const numValue = value === '' ? 0 : parseFloat(value) || 0
          day.tanks[tankName].content.push({ [grade]: numValue })
        }
        
        // Also update corresponding inventory by grade
        if (!day.inventory_by_grade[grade]) {
          day.inventory_by_grade[grade] = 0
        }
      }
    } 
    else {
      // Edit processing rates (still need to work with the original recipes)
      if (!day.processing_rates) {
        day.processing_rates = {}
      }
      const numValue = value === '' ? 0 : parseFloat(value) || 0
      day.processing_rates[key] = numValue
    }
    
    // Update edited schedule
    setEditedSchedule(newSchedule)
  }
  
  // Save changes back to the server
  const saveChanges = async () => {
    try {
      setSaveStatus('Saving...')
      
      await axios.post('/api/save-schedule', {
        schedule: editedSchedule
      })
      
      setSaveStatus('Saved successfully!')
      setTimeout(() => setSaveStatus(''), 3000)
      
      // Notify parent component if provided
      if (onScheduleChange) {
        onScheduleChange(editedSchedule)
      }
    } catch (error) {
      console.error('Error saving schedule:', error)
      setSaveStatus('Error saving changes')
      setTimeout(() => setSaveStatus(''), 3000)
    }
  }
  
  // Function to render the appropriate chart based on viewType
  const renderChart = () => {
    switch (viewType) {
      case 'processing':
        return (
          <BarChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="dayLabel" tick={{ fill: 'white' }} />
            <YAxis tick={{ fill: 'white' }} />
            <Tooltip 
              formatter={(value, name) => {
                // Format differently based on if it's a grade or recipe
                if (name.startsWith('grade_')) {
                  return [`${value.toFixed(1)}`, name.replace('grade_', '')]
                }
                return [`${value.toFixed(1)}`, name]
              }}
              labelFormatter={(label) => `Day ${label.split(' ')[1]}`}
            />
            <Legend 
              formatter={(value) => value.startsWith('grade_') ? value.replace('grade_', '') : value}
            />
            {/* Show grades consumed instead of recipes */}
            {processedGrades.map((grade, index) => (
              <Bar 
                key={grade}
                dataKey={`grade_${grade}`}
                name={`grade_${grade}`}
                stackId="stack"
                fill={gradeColors[index % gradeColors.length]}
                radius={[4, 4, 0, 0]}
              />
            ))}
          </BarChart>
        )
        
      case 'inventory':
        return (
          <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="dayLabel" tick={{ fill: 'white' }} />
            <YAxis tick={{ fill: 'white' }} />
            <Tooltip 
              formatter={(value, name) => [
                `${value.toFixed(1)}`, 
                name.startsWith('inventory_') ? name.replace('inventory_', '') : name
              ]}
              labelFormatter={(label) => `Day ${label.split(' ')[1]}`}
            />
            <Legend 
              formatter={(value) => value.startsWith('inventory_') ? value.replace('inventory_', '') : value}
            />
            {grades.map((grade, index) => (
              <Line
                key={grade}
                type="monotone"
                dataKey={`inventory_${grade}`}
                name={`inventory_${grade}`}
                stroke={gradeColors[index % gradeColors.length]}
                strokeWidth={2}
                dot={{ r: 4 }}
                activeDot={{ r: 6 }}
              />
            ))}
            <Line
              type="monotone"
              dataKey="totalInventory"
              name="Total Inventory"
              stroke="#000000"
              strokeWidth={3}
              dot={{ r: 4 }}
              activeDot={{ r: 6 }}
            />
          </LineChart>
        )
        
      case 'tanks':
        // tank chart remains the same
        return (
          <AreaChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="dayLabel" tick={{ fill: 'white' }} />
            <YAxis tick={{ fill: 'white' }} />
            <Tooltip 
              formatter={(value, name) => {
                const niceName = name.startsWith('tank_') 
                  ? name.replace('tank_', '').replace('_', ' - ')
                  : name
                return [`${value.toFixed(1)}`, niceName]
              }}
              labelFormatter={(label) => `Day ${label.split(' ')[1]}`}
            />
            <Legend 
              formatter={(value) => {
                if (value.startsWith('tank_')) {
                  const parts = value.split('_')
                  if (parts.length >= 3 && parts[2] === 'total') {
                    return `${parts[1]} (Total)`
                  } else if (parts.length >= 3) {
                    return `${parts[1]} - ${parts.slice(2).join('_')}`
                  }
                }
                return value
              }}
            />
            {tanks.map((tank, index) => (
              <Area
                key={tank}
                type="monotone"
                dataKey={`tank_${tank}_total`}
                name={`tank_${tank}_total`}
                fill={tankColors[index % tankColors.length]}
                stroke={tankColors[index % tankColors.length]}
                fillOpacity={0.6}
              />
            ))}
          </AreaChart>
        )
        
      default:
        return null
    }
  }

  return (
    <div className="h-full flex flex-col">
      {/* Add Dashboard Cards at the top */}
      <ScheduleDashboardCards schedule={schedule} originalSchedule={originalSchedule} />
      
      {/* Chart type selector */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <button 
          onClick={() => setViewType('processing')}
          className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
            viewType === 'processing' 
              ? '!bg-[#254E58] text-white' 
              : 'bg-[#88BDBC]/20 text-[#254E58] hover:bg-[#88BDBC]/30'
          }`}
        >
          Grade Processing
        </button>
        <button 
          onClick={() => setViewType('inventory')}
          className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
            viewType === 'inventory' 
              ? '!bg-[#254E58] text-white' 
              : 'bg-[#88BDBC]/20 text-[#254E58] hover:bg-[#88BDBC]/30'
          }`}
        >
          Inventory Levels
        </button>
        <button 
          onClick={() => setViewType('tanks')}
          className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
            viewType === 'tanks' 
              ? '!bg-[#254E58] text-white' 
              : 'bg-[#88BDBC]/20 text-[#254E58] hover:bg-[#88BDBC]/30'
          }`}
        >
          Tank Inventory
        </button>
        
        <div className="flex-grow"></div>
        
        <button 
          onClick={() => setShowDetails(!showDetails)}
          className={`px-3 py-1.5 rounded-md text-sm font-medium ${
            showDetails
              ? 'bg-white/30 text-white'
              : 'bg-white/20 text-white hover:bg-white/30'
          }`}
        >
          {showDetails ? 'Hide Details' : 'Show Details'}
        </button>
        
        <button 
          onClick={() => setEditMode(!editMode)}
          className={`px-3 py-1.5 rounded-md text-sm font-medium ${
            editMode
              ? '!bg-[#88BDBC] text-white'
              : 'bg-amber-100 text-amber-800 hover:bg-amber-200'
          }`}
        >
          {editMode ? 'Editing Mode' : 'Enable Editing'}
        </button>
        
        {editMode && (
          <button 
            onClick={saveChanges}
            className="px-3 py-1.5 rounded-md text-sm font-medium !bg-emerald-600 text-white hover:bg-emerald-700"
          >
            Save Changes
          </button>
        )}
        
        {saveStatus && (
          <span className={`px-3 py-1.5 text-sm ${
            saveStatus.includes('Error') ? 'text-red-600' : 'text-green-600'
          }`}>
            {saveStatus}
          </span>
        )}
      </div>

      {/* Chart display */}
      <div className="flex-grow mb-4 relative">
        <ResponsiveContainer width="100%" height="100%">
          {renderChart()}
        </ResponsiveContainer>
      </div>

      {/* Detailed data table - updated for processing view to show grades */}
      {showDetails && (
        <div className="h-64 overflow-y-auto border border-[#88BDBC]/30 rounded-md backdrop-blur-sm">
          <table className="min-w-full divide-y divide-[#88BDBC]/20">
            <thead className="bg-[#88BDBC] sticky top-0">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium text-white uppercase tracking-wider">Day</th>
                {viewType === 'processing' ? (
                  processedGrades.map(grade => (
                    <th key={grade} className="px-3 py-2 text-left text-xs font-medium text-white uppercase tracking-wider">
                      {grade}
                    </th>
                  ))
                ) : viewType === 'inventory' ? (
                  grades.map(grade => (
                    <th key={grade} className="px-3 py-2 text-left text-xs font-medium text-white uppercase tracking-wider">
                      {grade}
                    </th>
                  ))
                ) : (
                  tanks.map(tank => (
                    <th key={tank} className="px-3 py-2 text-left text-xs font-medium text-white uppercase tracking-wider">
                      {tank}
                    </th>
                  ))
                )}
                <th className="px-3 py-2 text-left text-xs font-medium text-white uppercase tracking-wider">
                  {viewType === 'processing' ? 'Total' : viewType === 'inventory' ? 'Total Inventory' : 'Total Tank Volume'}
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-[#88BDBC]/20">
              {chartData.map((day, idx) => (
                <tr 
                  key={day.day} 
                  className={`hover:bg-[#88BDBC]/10 ${
                    editMode ? 'bg-[#88BDBC]/5' : ''
                  }`}
                >
                  <td className="px-3 py-2 whitespace-nowrap text-sm text-[#254E58]">Day {day.day}</td>
                  {viewType === 'processing' ? (
                    processedGrades.map(grade => (
                      <td key={grade} className="px-3 py-2 whitespace-nowrap text-sm text-gray-600">
                        {editMode ? (
                          <div className="flex items-center">
                            <span className="text-[#254E58] text-xs px-2 py-1 bg-gray-100 rounded">
                              {day[`grade_${grade}`] ? day[`grade_${grade}`].toFixed(1) : '0.0'}
                            </span>
                            <span className="text-xs text-gray-400 ml-1">(calc)</span>
                          </div>
                        ) : (
                          day[`grade_${grade}`] ? day[`grade_${grade}`].toFixed(1) : '-'
                        )}
                      </td>
                    ))
                  ) : viewType === 'inventory' ? (
                    grades.map(grade => (
                      <td key={grade} className="px-3 py-2 whitespace-nowrap text-sm text-gray-600">
                        {editMode ? (
                          <input
                            type="number"
                            value={editedSchedule[idx]?.inventory_by_grade?.[grade] || ''}
                            onChange={(e) => handleValueChange(idx, `inventory_${grade}`, e.target.value)}
                            className="w-full px-2 py-1 border border-[#88BDBC]/30 rounded text-[#254E58] text-xs focus:outline-none focus:ring-2 focus:ring-[#88BDBC]/50"
                            step="0.1"
                            min="0"
                            placeholder="0.0"
                          />
                        ) : (
                          day[`inventory_${grade}`] ? day[`inventory_${grade}`].toFixed(1) : '-'
                        )}
                      </td>
                    ))
                  ) : (
                    tanks.map(tank => (
                      <td key={tank} className="px-3 py-2 whitespace-nowrap text-sm text-gray-600">
                        {editMode ? (
                          <div className="flex items-center">
                            <span className="text-[#254E58] text-xs px-2 py-1 bg-gray-100 rounded">
                              {day[`tank_${tank}_total`] ? day[`tank_${tank}_total`].toFixed(1) : '0.0'}
                            </span>
                            <span className="text-xs text-gray-400 ml-1">(calc)</span>
                          </div>
                        ) : (
                          day[`tank_${tank}_total`] ? day[`tank_${tank}_total`].toFixed(1) : '-'
                        )}
                      </td>
                    ))
                  )}
                  <td className="px-3 py-2 whitespace-nowrap text-sm font-medium text-[#254E58]">
                    {viewType === 'processing' 
                      ? day.totalProcessing.toFixed(1)
                      : viewType === 'inventory'
                        ? day.totalInventory.toFixed(1)
                        : Object.keys(day)
                            .filter(key => key.endsWith('_total'))
                            .reduce((sum, key) => sum + (day[key] || 0), 0)
                            .toFixed(1)
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      
      {editMode && (
        <div className="mt-4 p-3 bg-amber-50 border border-amber-200 rounded-md text-sm text-amber-800">
          <p className="font-medium">Editing Mode Instructions:</p>
          <ul className="list-disc ml-5 mt-1">
            <li>Enable "Show Details" to see the data table below the chart</li>
            <li><strong>Inventory View:</strong> Edit inventory levels directly in the table</li>
            <li><strong>Processing View:</strong> Grade consumption values are calculated (read-only)</li>
            <li><strong>Tank View:</strong> Tank totals are calculated from contents (read-only)</li>
            <li>Changes are made in real-time as you type</li>
            <li>Click "Save Changes" to persist your edits to the server</li>
          </ul>
        </div>
      )}
    </div>
  )
}

export default DailyPlanChart