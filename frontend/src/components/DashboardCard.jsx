import React from 'react';

// Named export for DashboardCard component
export const DashboardCard = ({ title, value, unit, change, icon, className = "" }) => {
  const getChangeColor = () => !change ? 'text-white/70' : change > 0 ? 'text-[#88BDBC]' : 'text-red-400';
  const getChangeIcon = () => !change ? '' : change > 0 ? '↑' : '↓';

  return (
    <div className={`bg-white/10 backdrop-blur-sm rounded-lg border border-white/20 p-3 hover:bg-white/15 transition-all duration-200 shadow-lg ${className}`}>
      <div className="flex items-center justify-between">
        <h3 className="text-white/80 text-xs font-medium">{title}</h3>
        {icon && <span className="text-sm text-[#88BDBC]">{icon}</span>}
      </div>
      <div className="mt-1">
        <div className="flex items-end">
          <p className="text-lg font-bold text-white">{value}</p>
          {unit && <p className="ml-1 text-white/70 text-xs">{unit}</p>}
        </div>
        {change !== undefined && (
          <p className={`text-xs ${getChangeColor()} flex items-center`}>
            <span>{getChangeIcon()}</span>
            <span className="ml-1">
              {Math.abs(change).toFixed(1)}% {change >= 0 ? 'better' : 'worse'}
            </span>
          </p>
        )}
      </div>
    </div>
  );
};

// Named export for the dashboard card collection for schedule data
export const ScheduleDashboardCards = ({ schedule, originalSchedule }) => {
  // Calculate metrics for current schedule
  const metrics = React.useMemo(() => {
    if (!schedule || schedule.length === 0) return null;
    
    let totalProcessingRate = 0;
    let daysWithProcessing = 0;
    let totalMargin = 0;
    
    for (const day of schedule) {
      const processingRates = day.processing_rates || {};
      const dayTotal = Object.values(processingRates).reduce((sum, rate) => sum + rate, 0);
      
      if (dayTotal > 0) {
        totalProcessingRate += dayTotal;
        daysWithProcessing++;
      }
      
      // Use the margin field if present
      if (typeof day.margin === 'number') {
        totalMargin += day.margin;
      } else {
        // fallback to old calculation if needed
        for (const [recipe, rate] of Object.entries(processingRates)) {
          const recipeDetails = day.blending_details?.find(r => r.name === recipe);
          if (recipeDetails && recipeDetails.margin) {
            totalMargin += rate * recipeDetails.margin;
          }
        }
      }
    }
    
    const avgProcessingRate = daysWithProcessing > 0 
      ? totalProcessingRate / daysWithProcessing 
      : 0;
    
    return {
      avgProcessingRate: avgProcessingRate.toFixed(1),
      totalMargin: totalMargin.toFixed(2),
      utilizationDays: daysWithProcessing,
      totalProcessed: totalProcessingRate.toFixed(1)
    };
  }, [schedule]);

  // Calculate original metrics for comparison
  const originalMetrics = React.useMemo(() => {
    if (!originalSchedule || originalSchedule.length === 0) return null;
    
    let totalProcessingRate = 0;
    let daysWithProcessing = 0;
    let totalMargin = 0;
    
    for (const day of originalSchedule) {
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
      totalMargin: totalMargin.toFixed(2),
      utilizationDays: daysWithProcessing,
      totalProcessed: totalProcessingRate.toFixed(1)
    };
  }, [originalSchedule]);

  // Calculate changes (if original metrics available)
  const rateChange = originalMetrics ? 
    ((parseFloat(metrics.avgProcessingRate) - parseFloat(originalMetrics.avgProcessingRate)) / 
      parseFloat(originalMetrics.avgProcessingRate) * 100) : undefined;
      
  const marginChange = originalMetrics ?
    ((parseFloat(metrics.totalMargin) - parseFloat(originalMetrics.totalMargin)) / 
      parseFloat(originalMetrics.totalMargin) * 100) : undefined;
      
  const utilizationChange = originalMetrics ?
    ((metrics.utilizationDays - originalMetrics.utilizationDays) / 
      originalMetrics.utilizationDays * 100) : undefined;

  if (!metrics) return null;

  return (
    <div className="grid grid-cols-4 gap-2 mb-4">
      <DashboardCard 
        title="Avg. Processing" 
        value={metrics.avgProcessingRate} 
        unit="kb/d"
        change={rateChange}
        icon="🏭"
      />
      <DashboardCard 
        title="Total Processed" 
        value={metrics.totalProcessed} 
        unit="kb"
        icon="⛽"
      />
      <DashboardCard 
        title="Total Margin" 
        value={metrics.totalMargin} 
        unit="$K"
        change={marginChange}
        icon="💰"
      />
      <DashboardCard 
        title="Processing Days" 
        value={metrics.utilizationDays}
        unit=""
        change={utilizationChange}
        icon="📆"
      />
    </div>
  );
};

// Named export for vessel dashboard cards
export const VesselDashboardCards = ({ vessels }) => {
  // Calculate vessel metrics
  const metrics = React.useMemo(() => {
    if (!vessels || vessels.length === 0) return null;
    
    // Convert to array if it's an object
    const vesselsArray = Array.isArray(vessels) ? vessels : Object.values(vessels);
    
    let totalVolume = 0;
    let earliestArrival = Infinity;
    let latestArrival = 0;
    const crudeTypes = new Set();
    
    for (const vessel of vesselsArray) {
      // Sum cargo volumes
      if (vessel.cargo) {
        for (const cargo of vessel.cargo) {
          totalVolume += parseFloat(cargo.volume || 0);
          if (cargo.grade) crudeTypes.add(cargo.grade);
        }
      } else if (vessel.volume) {
        totalVolume += parseFloat(vessel.volume || 0);
      }
      
      // Track arrival timeline
      const arrivalDay = parseInt(vessel.arrival_day || 0);
      if (arrivalDay < earliestArrival) earliestArrival = arrivalDay;
      if (arrivalDay > latestArrival) latestArrival = arrivalDay;
    }
    
    return {
      vesselCount: vesselsArray.length,
      totalVolume: totalVolume.toFixed(0),
      crudeTypes: crudeTypes.size,
      deliverySpan: earliestArrival < Infinity ? `${earliestArrival}-${latestArrival}` : "N/A"
    };
  }, [vessels]);

  if (!metrics) return null;

  return (
    <div className="grid grid-cols-4 gap-2 mb-4">
      <DashboardCard 
        title="Vessel Count" 
        value={metrics.vesselCount} 
        icon="🚢"
      />
      <DashboardCard 
        title="Total Volume" 
        value={metrics.totalVolume} 
        unit="kb"
        icon="⛽"
      />
      <DashboardCard 
        title="Crude Types" 
        value={metrics.crudeTypes} 
        icon="🧪"
      />
      <DashboardCard 
        title="Delivery Days" 
        value={metrics.deliverySpan}
        icon="📆"
      />
    </div>
  );
};

// Default export (optional)
export default DashboardCard;