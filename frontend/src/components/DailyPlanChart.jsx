import { useState, useEffect } from 'react'
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line, AreaChart, Area } from 'recharts'
import axios from 'axios'

function DailyPlanChart({ schedule, onScheduleChange }) {
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
        <p className="text-slate-500">No schedule data available.</p>
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
  
  // Generate colors for different data series
  const recipeColors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']
  const gradeColors = ['#0ea5e9', '#22c55e', '#f97316', '#ec4899', '#6366f1']
  const tankColors = ['#4ade80', '#60a5fa', '#f472b6', '#fb923c', '#94a3b8', '#c084fc']
  
  // Handle value edit in table
  const handleValueChange = (dayIndex, key, value) => {
    // Copy the schedule to avoid direct mutation
    const newSchedule = [...editedSchedule]
    const day = newSchedule[dayIndex]
    
    // Handle different data types
    if (key.startsWith('inventory_')) {
      // Edit inventory by grade
      const grade = key.replace('inventory_', '')
      day.inventory_by_grade = { ...day.inventory_by_grade, [grade]: parseFloat(value) }
      
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
          day.tanks[tankName].content[contentIndex] = { [grade]: parseFloat(value) }
        } else {
          day.tanks[tankName].content.push({ [grade]: parseFloat(value) })
        }
        
        // Also update corresponding inventory by grade
        if (!day.inventory_by_grade[grade]) {
          day.inventory_by_grade[grade] = 0
        }
      }
    } 
    else {
      // Edit processing rates (still need to work with the original recipes)
      day.processing_rates = { ...day.processing_rates, [key]: parseFloat(value) }
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
            <XAxis dataKey="dayLabel" />
            <YAxis />
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
                onClick={(data) => editMode && setSelectedDay(data.day - 1)}
              />
            ))}
          </BarChart>
        )
        
      case 'inventory':
        return (
          <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="dayLabel" />
            <YAxis />
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
                onClick={(data) => editMode && setSelectedDay(data.day - 1)}
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
            <XAxis dataKey="dayLabel" />
            <YAxis />
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
                onClick={(data) => {
                  if (editMode) {
                    setSelectedDay(data.day - 1)
                    setSelectedTank(tank)
                  }
                }}
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
      {/* Chart type selector */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <button 
          onClick={() => setViewType('processing')}
          className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
            viewType === 'processing' 
              ? '!bg-emerald-600 text-white' 
              : 'bg-blue-50 text-blue-800 hover:bg-blue-100'
          }`}
        >
          Grade Processing
        </button>
        <button 
          onClick={() => setViewType('inventory')}
          className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
            viewType === 'inventory' 
              ? '!bg-emerald-600 text-white' 
              : 'bg-blue-50 text-blue-800 hover:bg-blue-100'
          }`}
        >
          Inventory Levels
        </button>
        <button 
          onClick={() => setViewType('tanks')}
          className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
            viewType === 'tanks' 
              ? '!bg-emerald-600 text-white' 
              : 'bg-blue-50 text-blue-800 hover:bg-blue-100'
          }`}
        >
          Tank Inventory
        </button>
        
        <div className="flex-grow"></div>
        
        <button 
          onClick={() => setShowDetails(!showDetails)}
          className={`px-3 py-1.5 rounded-md text-sm font-medium ${
            showDetails
              ? 'bg-slate-200 text-slate-800'
              : 'bg-slate-100 text-slate-700 hover:bg-slate-200'
          }`}
        >
          {showDetails ? 'Hide Details' : 'Show Details'}
        </button>
        
        <button 
          onClick={() => setEditMode(!editMode)}
          className={`px-3 py-1.5 rounded-md text-sm font-medium ${
            editMode
              ? '!bg-blue-500 text-white'
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
        
        {/* Edit tooltip if in edit mode and day selected */}
        {editMode && selectedDay !== null && (
          <div className="absolute top-4 right-4 bg-white p-4 rounded-lg shadow-lg border border-slate-200 max-w-md">
            <div className="flex justify-between items-center mb-2">
              <h3 className="font-semibold">Editing Day {editedSchedule[selectedDay]?.day}</h3>
              <button 
                onClick={() => setSelectedDay(null)}
                className="text-slate-500 hover:text-slate-700"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 011.414 1.414L11.414 10l4.293 4.293a1 1 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 01-1.414-1.414L8.586 10 4.293 5.707a1 1 010-1.414z" clipRule="evenodd" />
                </svg>
              </button>
            </div>
            
            {viewType === 'processing' && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-slate-600">Recipe Processing Rates</h4>
                {recipes.map((recipe) => (
                  <div key={recipe} className="flex items-center gap-2">
                    <div 
                      className="w-3 h-3 rounded-full" 
                      style={{ backgroundColor: recipeColors[recipes.indexOf(recipe) % recipeColors.length] }}
                    ></div>
                    <label className="text-sm">{recipe}:</label>
                    <input
                      type="number"
                      value={editedSchedule[selectedDay]?.processing_rates?.[recipe] || 0}
                      onChange={(e) => handleValueChange(selectedDay, recipe, e.target.value)}
                      className="border border-slate-300 rounded px-2 py-1 text-sm w-24"
                      step="0.1"
                      min="0"
                    />
                  </div>
                ))}
                
                <h4 className="text-sm font-medium text-slate-600 mt-4">Resulting Grade Processing</h4>
                {processedGrades.map((grade) => {
                  const gradeConsumption = calculateGradeConsumption(editedSchedule[selectedDay]);
                  return (
                    <div key={grade} className="flex items-center gap-2">
                      <div 
                        className="w-3 h-3 rounded-full" 
                        style={{ backgroundColor: gradeColors[processedGrades.indexOf(grade) % gradeColors.length] }}
                      ></div>
                      <label className="text-sm">{grade}:</label>
                      <span className="text-sm">{(gradeConsumption[grade] || 0).toFixed(1)}</span>
                    </div>
                  );
                })}
              </div>
            )}
            
            {viewType === 'inventory' && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-slate-600">Inventory Levels</h4>
                {grades.map((grade) => (
                  <div key={grade} className="flex items-center gap-2">
                    <div 
                      className="w-3 h-3 rounded-full" 
                      style={{ backgroundColor: gradeColors[grades.indexOf(grade) % gradeColors.length] }}
                    ></div>
                    <label className="text-sm">{grade}:</label>
                    <input
                      type="number"
                      value={editedSchedule[selectedDay]?.inventory_by_grade?.[grade] || 0}
                      onChange={(e) => handleValueChange(selectedDay, `inventory_${grade}`, e.target.value)}
                      className="border border-slate-300 rounded px-2 py-1 text-sm w-24"
                      step="0.1"
                      min="0"
                    />
                  </div>
                ))}
              </div>
            )}
            
            {viewType === 'tanks' && selectedTank && (
              <div className="space-y-2">
                <h4 className="text-sm font-medium text-slate-600">Tank {selectedTank} Contents</h4>
                {(editedSchedule[selectedDay]?.tanks?.[selectedTank]?.content || []).map((content, idx) => {
                  const grade = Object.keys(content)[0];
                  return (
                    <div key={idx} className="flex items-center gap-2">
                      <div 
                        className="w-3 h-3 rounded-full" 
                        style={{ backgroundColor: gradeColors[idx % gradeColors.length] }}
                      ></div>
                      <label className="text-sm">{grade}:</label>
                      <input
                        type="number"
                        value={content[grade] || 0}
                        onChange={(e) => handleValueChange(
                          selectedDay, 
                          `tank_${selectedTank}_${grade}`, 
                          e.target.value
                        )}
                        className="border border-slate-300 rounded px-2 py-1 text-sm w-24"
                        step="0.1"
                        min="0"
                      />
                    </div>
                  );
                })}
                <button
                  className="text-sm text-blue-600 hover:text-blue-700 flex items-center gap-1"
                  onClick={() => {
                    const newSchedule = [...editedSchedule];
                    const day = newSchedule[selectedDay];
                    if (!day.tanks[selectedTank].content) {
                      day.tanks[selectedTank].content = [];
                    }
                    day.tanks[selectedTank].content.push({ "New Grade": 0 });
                    setEditedSchedule(newSchedule);
                  }}
                >
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                  Add Grade
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Detailed data table - updated for processing view to show grades */}
      {showDetails && (
        <div className="h-64 overflow-y-auto border border-slate-200 rounded-md">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50 sticky top-0">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Day</th>
                {viewType === 'processing' ? (
                  processedGrades.map(grade => (
                    <th key={grade} className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      {grade}
                    </th>
                  ))
                ) : viewType === 'inventory' ? (
                  grades.map(grade => (
                    <th key={grade} className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      {grade}
                    </th>
                  ))
                ) : (
                  tanks.map(tank => (
                    <th key={tank} className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      {tank}
                    </th>
                  ))
                )}
                <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                  {viewType === 'processing' ? 'Total' : viewType === 'inventory' ? 'Total Inventory' : 'Total Tank Volume'}
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-slate-200">
              {chartData.map((day, idx) => (
                <tr 
                  key={day.day} 
                  className={`hover:bg-slate-50 ${
                    editMode && selectedDay === idx ? 'bg-blue-50' : ''
                  }`}
                  onClick={() => editMode && setSelectedDay(idx)}
                >
                  <td className="px-3 py-2 whitespace-nowrap text-sm text-slate-900">Day {day.day}</td>
                  {viewType === 'processing' ? (
                    processedGrades.map(grade => (
                      <td key={grade} className="px-3 py-2 whitespace-nowrap text-sm text-slate-500">
                        {day[`grade_${grade}`] ? day[`grade_${grade}`].toFixed(1) : '-'}
                      </td>
                    ))
                  ) : viewType === 'inventory' ? (
                    grades.map(grade => (
                      <td key={grade} className="px-3 py-2 whitespace-nowrap text-sm text-slate-500">
                        {editMode ? (
                          <input
                            type="number"
                            value={day[`inventory_${grade}`] || 0}
                            onChange={(e) => handleValueChange(idx, `inventory_${grade}`, e.target.value)}
                            className="w-full px-2 py-1 border border-slate-300 rounded"
                            step="0.1"
                            min="0"
                          />
                        ) : (
                          day[`inventory_${grade}`] ? day[`inventory_${grade}`].toFixed(1) : '-'
                        )}
                      </td>
                    ))
                  ) : (
                    tanks.map(tank => (
                      <td key={tank} className="px-3 py-2 whitespace-nowrap text-sm text-slate-500">
                        {day[`tank_${tank}_total`] ? day[`tank_${tank}_total`].toFixed(1) : '-'}
                      </td>
                    ))
                  )}
                  <td className="px-3 py-2 whitespace-nowrap text-sm font-medium text-slate-900">
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
            <li>Click on the chart or table rows to select a day to edit</li>
            <li>Modify values directly in the table or in the edit panel</li>
            <li>Click "Save Changes" to persist your edits</li>
            <li>Tank inventory values are calculated from individual grade contents</li>
          </ul>
        </div>
      )}
    </div>
  )
}

export default DailyPlanChart