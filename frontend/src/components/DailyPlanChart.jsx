import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, LineChart, Line } from 'recharts'
import { useState } from 'react'

function DailyPlanChart({ schedule }) {
  const [viewType, setViewType] = useState('processing')
  const [showDetails, setShowDetails] = useState(false)
  
  // Early return if no schedule data
  if (!schedule || schedule.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <p className="text-slate-500">No schedule data available.</p>
      </div>
    )
  }
  
  // Process data for charts
  const chartData = schedule.map(day => {
    // Get total processing amount and per-recipe amounts
    const processingRates = {}
    let totalProcessing = 0
    
    Object.entries(day.processing_rates || {}).forEach(([recipe, rate]) => {
      processingRates[recipe] = rate
      totalProcessing += rate
    })
    
    // Get inventory by grade
    const inventoryByGrade = {}
    let totalInventory = 0
    
    Object.entries(day.inventory_by_grade || {}).forEach(([grade, amount]) => {
      inventoryByGrade[grade] = amount
      totalInventory += amount
    })
    
    return {
      day: day.day,
      dayLabel: `Day ${day.day}`,
      totalProcessing,
      totalInventory,
      ...processingRates,
      ...Object.entries(inventoryByGrade).reduce((acc, [grade, amount]) => {
        acc[`inventory_${grade}`] = amount
        return acc
      }, {})
    }
  })
  
  // Get unique recipe names for bars
  const recipes = [...new Set(
    schedule.flatMap(day => 
      Object.keys(day.processing_rates || {})
    )
  )]
  
  // Get unique crude grades for inventory
  const grades = [...new Set(
    schedule.flatMap(day => 
      Object.keys(day.inventory_by_grade || {})
    )
  )]
  
  // Generate colors for different data series
  const recipeColors = ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6']
  const gradeColors = ['#0ea5e9', '#22c55e', '#f97316', '#ec4899', '#6366f1']
  
  return (
    <div className="h-full flex flex-col">
      {/* Chart type selector */}
      <div className="flex gap-3 mb-4">
        <button 
          onClick={() => setViewType('processing')}
          className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
            viewType === 'processing' 
              ? 'bg-blue-600 text-white' 
              : 'bg-blue-50 text-blue-800 hover:bg-blue-100'
          }`}
        >
          Processing Rates
        </button>
        <button 
          onClick={() => setViewType('inventory')}
          className={`px-3 py-1.5 rounded-md text-sm font-medium transition ${
            viewType === 'inventory' 
              ? 'bg-blue-600 text-white' 
              : 'bg-blue-50 text-blue-800 hover:bg-blue-100'
          }`}
        >
          Inventory Levels
        </button>
        <div className="flex-grow"></div>
        <button 
          onClick={() => setShowDetails(!showDetails)}
          className="px-3 py-1.5 rounded-md text-sm font-medium bg-slate-100 text-slate-700 hover:bg-slate-200"
        >
          {showDetails ? 'Hide Details' : 'Show Details'}
        </button>
      </div>

      {/* Chart display */}
      <div className="flex-grow mb-4">
        <ResponsiveContainer width="100%" height="100%">
          {viewType === 'processing' ? (
            <BarChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <XAxis dataKey="dayLabel" />
              <YAxis />
              <Tooltip 
                formatter={(value, name) => [`${value.toFixed(1)}`, name]}
                labelFormatter={(label) => `Day ${label.split(' ')[1]}`}
              />
              <Legend />
              {recipes.map((recipe, index) => (
                <Bar 
                  key={recipe}
                  dataKey={recipe}
                  name={recipe}
                  stackId="stack"
                  fill={recipeColors[index % recipeColors.length]}
                  radius={[4, 4, 0, 0]}
                />
              ))}
            </BarChart>
          ) : (
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
          )}
        </ResponsiveContainer>
      </div>

      {/* Detailed data table (conditionally shown) */}
      {showDetails && (
        <div className="h-64 overflow-y-auto border border-slate-200 rounded-md">
          <table className="min-w-full divide-y divide-slate-200">
            <thead className="bg-slate-50 sticky top-0">
              <tr>
                <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">Day</th>
                {viewType === 'processing' ? (
                  recipes.map(recipe => (
                    <th key={recipe} className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      {recipe}
                    </th>
                  ))
                ) : (
                  grades.map(grade => (
                    <th key={grade} className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                      {grade}
                    </th>
                  ))
                )}
                <th className="px-3 py-2 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">
                  {viewType === 'processing' ? 'Total' : 'Total Inventory'}
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-slate-200">
              {chartData.map(day => (
                <tr key={day.day} className="hover:bg-slate-50">
                  <td className="px-3 py-2 whitespace-nowrap text-sm text-slate-900">Day {day.day}</td>
                  {viewType === 'processing' ? (
                    recipes.map(recipe => (
                      <td key={recipe} className="px-3 py-2 whitespace-nowrap text-sm text-slate-500">
                        {day[recipe] ? day[recipe].toFixed(1) : '-'}
                      </td>
                    ))
                  ) : (
                    grades.map(grade => (
                      <td key={grade} className="px-3 py-2 whitespace-nowrap text-sm text-slate-500">
                        {day[`inventory_${grade}`] ? day[`inventory_${grade}`].toFixed(1) : '-'}
                      </td>
                    ))
                  )}
                  <td className="px-3 py-2 whitespace-nowrap text-sm font-medium text-slate-900">
                    {viewType === 'processing' 
                      ? day.totalProcessing.toFixed(1)
                      : day.totalInventory.toFixed(1)
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default DailyPlanChart