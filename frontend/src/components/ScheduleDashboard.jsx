import React, { useMemo } from 'react';
import DashboardCard from './DashboardCard';

const ScheduleDashboard = ({ 
  scheduleData, 
  optimizedScheduleData = null,
  vessels = [] 
}) => {
  // Calculate metrics from schedule data
  const metrics = useMemo(() => {
    if (!scheduleData || scheduleData.length === 0) return null;
    
    // Calculate average processing rate
    let totalProcessingRate = 0;
    let daysWithProcessing = 0;
    
    // Calculate total margin
    let totalMargin = 0;
    
    for (const day of scheduleData) {
      const processingRates = day.processing_rates || {};
      const dayTotal = Object.values(processingRates).reduce((sum, rate) => sum + rate, 0);
      
      if (dayTotal > 0) {
        totalProcessingRate += dayTotal;
        daysWithProcessing++;
      }
      
      // Calculate margin for each recipe processed
      for (const [recipe, rate] of Object.entries(processingRates)) {
        // Find the recipe in blending_details to get margin info
        const recipeDetails = day.blending_details?.find(r => r.name === recipe);
        if (recipeDetails && recipeDetails.margin) {
          totalMargin += rate * recipeDetails.margin;
        }
      }
    }
    
    const avgProcessingRate = daysWithProcessing > 0 
      ? totalProcessingRate / daysWithProcessing 
      : 0;
    
    return {
      avgProcessingRate: avgProcessingRate.toFixed(1),
      vesselCount: vessels.length,
      totalMargin: totalMargin.toFixed(2),
      utilizationDays: daysWithProcessing
    };
  }, [scheduleData, vessels]);
  
  // Calculate optimized metrics
  const optimizedMetrics = useMemo(() => {
    if (!optimizedScheduleData || optimizedScheduleData.length === 0) return null;
    
    // Similar calculation as above for optimized data
    let totalProcessingRate = 0;
    let daysWithProcessing = 0;
    let totalMargin = 0;
    
    for (const day of optimizedScheduleData) {
      const processingRates = day.processing_rates || {};
      const dayTotal = Object.values(processingRates).reduce((sum, rate) => sum + rate, 0);
      
      if (dayTotal > 0) {
        totalProcessingRate += dayTotal;
        daysWithProcessing++;
      }
      
      for (const [recipe, rate] of Object.entries(processingRates)) {
        const recipeDetails = day.blending_details?.find(r => r.name === recipe);
        if (recipeDetails && recipeDetails.margin) {
          totalMargin += rate * recipeDetails.margin;
        }
      }
    }
    
    const avgProcessingRate = daysWithProcessing > 0 
      ? totalProcessingRate / daysWithProcessing 
      : 0;
    
    return {
      avgProcessingRate: avgProcessingRate.toFixed(1),
      vesselCount: vessels.length,
      totalMargin: totalMargin.toFixed(2),
      utilizationDays: daysWithProcessing
    };
  }, [optimizedScheduleData, vessels]);
  
  // Calculate percentage changes
  const getPercentChange = (original, optimized) => {
    if (!original || !optimized || parseFloat(original) === 0) return 0;
    return ((parseFloat(optimized) - parseFloat(original)) / parseFloat(original)) * 100;
  };
  
  // If no data, show placeholder
  if (!metrics) {
    return (
      <div className="bg-white rounded-lg shadow-md p-4">
        <p className="text-gray-500">Run the scheduler to see metrics</p>
      </div>
    );
  }
  
  const hasOptimizedData = optimizedMetrics !== null;
  
  const rateChange = hasOptimizedData 
    ? getPercentChange(metrics.avgProcessingRate, optimizedMetrics.avgProcessingRate) 
    : undefined;
    
  const marginChange = hasOptimizedData 
    ? getPercentChange(metrics.totalMargin, optimizedMetrics.totalMargin) 
    : undefined;
    
  const utilizationChange = hasOptimizedData 
    ? getPercentChange(metrics.utilizationDays, optimizedMetrics.utilizationDays) 
    : undefined;

  return (
    <div className="dashboard-container">
      <h2 className="text-lg font-semibold mb-4">Schedule Performance</h2>
      
      <div className="grid grid-cols-2 gap-2">
        <DashboardCard 
          title="Avg. Processing" 
          value={hasOptimizedData ? optimizedMetrics.avgProcessingRate : metrics.avgProcessingRate} 
          unit="kb/d"
          change={rateChange}
          icon="🏭"
        />
        
        <DashboardCard 
          title="Vessels" 
          value={metrics.vesselCount} 
          unit=""
          icon="🚢"
        />
        
        <DashboardCard 
          title="Total Margin" 
          value={hasOptimizedData ? optimizedMetrics.totalMargin : metrics.totalMargin} 
          unit="$K"
          change={marginChange}
          icon="💰"
        />
        
      </div>
    </div>
  );
};

export default ScheduleDashboard;