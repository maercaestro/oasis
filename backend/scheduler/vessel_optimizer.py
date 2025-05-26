"""
Vessel Optimizer class using time-space network model.
Optimizes vessel scheduling and feedstock delivery by solving a minimum cost flow problem.

Copyright (c) by Abu Huzaifah Bidin
"""

import json
import os
from typing import List, Dict, Optional, Tuple, Set
import networkx as nx
import pulp as plp
import matplotlib.pyplot as plt
from .models import Vessel, FeedstockParcel, FeedstockRequirement, Route
import copy # Added import

MAX_VESSELS = 5  # Maximum number of vessels allowed in the network
DEFAULT_COST_PER_DEPLOYED_VESSEL = 1000  # Example cost for deploying one vessel
DEFAULT_PENALTY_PER_UNMET_REQUIREMENT = 100000 # Example high penalty for an unmet requirement

class VesselOptimizer:
    """
    Optimizer for vessel scheduling and feedstock delivery.
    Uses time-space network model to minimize total
    vessel cost while ensuring all feedstock requirements are met.
    """
    
    def __init__(self, feedstock_requirements: List[FeedstockRequirement], 
                 routes: Dict[str, Route],
                 vessel_types: List[Dict]):
        """
        Initialize the vessel optimizer.
        
        Args:
            feedstock_requirements: List of feedstock requirements to be fulfilled
            routes: Dictionary of routes (key format: "{origin}_{destination}")
            vessel_types: List of available vessel types with their capacities and costs
        """
        self.requirements = feedstock_requirements
        self.routes = routes
        self.vessel_types = vessel_types
        self.locations = self._extract_locations()
        
    def _extract_locations(self) -> List[str]:
        """Extract all unique locations from requirements and routes"""
        locations = set()
        
        # Add requirement origins
        for req in self.requirements:
            locations.add(req.origin)
        
        # Add refinery as a special location
        locations.add("Refinery")
        
        return list(locations)
    
    def optimize(self, horizon_days: int = 30, time_limit_seconds: int = 3000, mip_gap: float = 0.05,
                 cost_per_deployed_vessel: float = DEFAULT_COST_PER_DEPLOYED_VESSEL,
                 penalty_per_unmet_requirement: float = DEFAULT_PENALTY_PER_UNMET_REQUIREMENT) -> List[Vessel]:
        """Optimize vessel scheduling to minimize costs using PuLP"""
        # Build time-space network
        network = self._build_time_space_network(horizon_days, cost_per_deployed_vessel)
        print(f"Network created with {len(network.nodes())} nodes and {len(network.edges())} edges")
        
        # Create PuLP model
        model = plp.LpProblem("VesselSchedulingWithPenalties", plp.LpMinimize)
        
        # Create flow variables for each edge in the network
        flow_vars = {}
        for u, v, data in network.edges(data=True):
            var_name = f"flow_{str(u).replace(' ','_')}_{str(v).replace(' ','_')}"
            var_name = var_name.replace(',','_').replace('(','').replace(')','').replace("'","")
            flow_vars[(u, v)] = plp.LpVariable(var_name, lowBound=0, upBound=data['capacity'], cat='Integer')
        
        # Define objective function: minimize vessel deployment costs + penalties for unmet requirements
        
        vessel_deployment_cost_term = plp.lpSum(
            flow_vars[(u, v)] * data['cost'] 
            for u, v, data in network.edges(data=True) 
            if data.get('action') == 'deploy_vessel' and 'cost' in data
        )
        
        # Slack variable for unmet requirements
        num_unmet_requirements_slack = plp.LpVariable(
            "NumUnmetRequirementsSlack", 
            lowBound=0, 
            upBound=len(self.requirements), 
            cat='Integer'
        )
        
        penalty_cost_term = num_unmet_requirements_slack * penalty_per_unmet_requirement
        
        model += vessel_deployment_cost_term + penalty_cost_term, "Minimize_Vessel_And_Penalty_Costs"
        
        # Add flow conservation constraints
        for node in network.nodes():
            demand = network.nodes[node].get('demand', 0)
            incoming_flow = plp.lpSum(flow_vars[(u, node)] for u in network.predecessors(node) if (u, node) in flow_vars)
            outgoing_flow = plp.lpSum(flow_vars[(node, v)] for v in network.successors(node) if (node, v) in flow_vars)

            if node == 'sink':
                # Sink fulfillment: incoming flow + unmet slack == total requirement demand
                # The sink's 'demand' attribute stores len(self.requirements)
                model += incoming_flow + num_unmet_requirements_slack == demand, "Sink_Fulfillment_Balance"
            elif node == 'source':
                 # Source supplies flow: incoming - outgoing == negative demand (supply)
                model += incoming_flow - outgoing_flow == demand, f"Flow_Demand_{str(node).replace(' ','_')}"
            else: # Transit nodes
                if demand != 0: # Should be 0 for transit nodes as defined
                    print(f"Warning: Transit node {node} has non-zero demand {demand}. Treating as conservation.")
                model += incoming_flow - outgoing_flow == demand, f"Flow_Conservation_{str(node).replace(' ','_')}"
        
        # ENFORCE: Each requirement must be assigned to a vessel (link requirement_flow to vessel deployment)
        # REMOVING THIS CONSTRAINT - It's complex and might cause infeasibility.
        # The source/sink demand and requirement_flow capacity=1 should handle fulfillment.
        # for u, v, data in network.edges(data=True):
        #     if data.get('action') == 'requirement_flow':
        #         loading_node = v # This should be loading_node = u, as (u,v) is requirement_flow
        #         # Find all edges entering this loading_node (should be only one: from (origin, start_day))
        #         enter_edges = [key for key in flow_vars if key[1] == loading_node and network.get_edge_data(*key).get('action') == 'enter_loading']
        #         if enter_edges:
        #             model += flow_vars[(u, v)] == plp.lpSum(flow_vars[edge] for edge in enter_edges), f"ReqVesselLink_{str(loading_node)}"

        # ENFORCE: Vessel capacity constraints (no vessel overloaded)
        # REMOVING THIS CONSTRAINT - This is not formulated correctly for a network flow model.
        # Vessel capacity is handled during the extraction phase.
        # for u, v, data in network.edges(data=True):
        #     if data.get('action') == 'deploy_vessel':
        #         loading_node = v
        #         req_edges = [key for key in flow_vars if key[1] == loading_node and network.get_edge_data(*key).get('action') == 'requirement_flow']
        #         if req_edges:
        #             model += plp.lpSum(flow_vars[edge] * network.get_edge_data(*edge).get('req').volume for edge in req_edges) <= data['capacity'], f"VesselCapacity_{str(loading_node)}"
        
        # Vessel limit constraints - ensure we use at most MAX_VESSELS
        vessel_deployment_vars = []
        for u, v, data in network.edges(data=True):
            if data.get('action', '').startswith('deploy_vessel'): # Catches deploy_vessel and deploy_vessel_penalty
                vessel_deployment_vars.append(flow_vars[(u, v)])
        
        if vessel_deployment_vars: # Ensure there are deployment variables before adding constraint
            model += plp.lpSum(vessel_deployment_vars) <= MAX_VESSELS, "Global_Vessel_Limit"
        
        # Prioritize regular deployments over penalty deployments
        # The objective function already handles costs. If penalty deployments have higher costs, they'll be disfavored.
        # The Global_Vessel_Limit applies to all types of deployments counted in vessel_deployment_vars.
        # Removing the separate Regular_Deployment_Limit as Global_Vessel_Limit is more encompassing.
        # regular_deployments = []
        # penalty_deployments = []
        # for u, v, data in network.edges(data=True):
        #     if data.get('action') == 'deploy_vessel':
        #         regular_deployments.append(flow_vars[(u, v)])
        #     elif data.get('action', '').startswith('deploy_vessel_penalty'):
        #         penalty_deployments.append(flow_vars[(u, v)])
        
        # if regular_deployments:
        #     model += plp.lpSum(regular_deployments) <= MAX_VESSELS, "Regular_Deployment_Limit" # Changed 5 to MAX_VESSELS
        
        # Configure solver with MIP gap
        # CBC solver uses gapRel for MIP gap - tells solver to stop when solution is within this % of optimal
        solver = plp.PULP_CBC_CMD(
            timeLimit=time_limit_seconds,
            msg=True,
            gapRel=mip_gap  # Added MIP gap parameter (5% default)
            # Removed problematic options: options=['allowable_gap', str(mip_gap * 100)]
        )
        
        # Solve the model
        print(f"Starting PuLP optimization with {mip_gap*100}% MIP gap tolerance...")
        try:
            status = model.solve(solver)
            print(f"Optimization status: {plp.LpStatus[status]} (code: {status})")
            
            # FIXED: Check against correct PuLP status constants
            if status != plp.LpStatusOptimal:
                print(f"Warning: Solution is not optimal. Status: {plp.LpStatus[status]}")
                
                # If infeasible, try to diagnose the issue
                if status == plp.LpStatusInfeasible:
                    print("Model is infeasible - checking for reasons...")
                    # Try relaxing some constraints for diagnosis
                    try:
                        # Create a relaxed model for diagnosis
                        relaxed_model = plp.LpProblem("RelaxedVesselScheduling", plp.LpMinimize)
                        relaxed_model += plp.lpSum(flow_vars[(u, v)] * data['cost'] 
                                      for u, v, data in network.edges(data=True))
                        
                        # Add relaxed flow conservation constraints
                        for node in network.nodes():
                            demand = network.nodes[node].get('demand', 0)
                            incoming = sum(flow_vars[(u, node)] for u in network.predecessors(node) 
                                          if (u, node) in flow_vars)
                            outgoing = sum(flow_vars[(node, v)] for v in network.successors(node) 
                                          if (node, v) in flow_vars)
                            
                            # Relaxed constraint with slack variables
                            slack_var = plp.LpVariable(f"slack_{str(node).replace(' ','_')}", 0, None)
                            relaxed_model += incoming - outgoing == demand + slack_var
                        
                        relaxed_model.solve()
                        print(f"Relaxed model status: {plp.LpStatus[relaxed_model.status]}")
                        
                        # Check which slack variables are non-zero
                        for var in relaxed_model.variables():
                            if var.name.startswith("slack_") and var.value() > 0:
                                print(f"Infeasibility at node: {var.name[6:]} (slack: {var.value()})")
                        
                    except Exception as e:
                        print(f"Error in relaxation analysis: {e}")
                    
            # Allow even infeasible solutions to proceed with extraction
            if status == plp.LpStatusInfeasible:
                print("WARNING: Proceeding with extraction despite infeasible status")
                
        except Exception as e:
            print(f"Error solving model: {e}")
            return []
        
        # Convert PuLP solution to flow dictionary format
        flow_dict = {}
        for (u, v), var in flow_vars.items():
            if var.value() and var.value() > 0:  # Check if value exists and is positive
                if u not in flow_dict:
                    flow_dict[u] = {}
                flow_dict[u][v] = var.value()
        
        # Print solution summary
        if status == plp.LpStatusOptimal or flow_dict:  # Check if we have a solution
            print(f"Objective function value: {plp.value(model.objective)}")
            total_flow = sum(sum(flows.values()) for flows in flow_dict.values())
            print(f"Total flow in solution: {total_flow}")
            
            # Visualize solution details
            self.visualize_solution(model, flow_vars, network)
            
            # Extract vessels from solution
            vessels = self._extract_solution_from_flow(network, flow_dict, horizon_days)
            return vessels
        else:
            print("No feasible solution found")
            return []
    
    def _build_time_space_network(self, horizon_days: int, cost_per_deployed_vessel: float) -> nx.DiGraph:
        """Build a minimal time-space network for vessel scheduling and requirements."""
        G = nx.DiGraph()
        G.add_node('source', demand=-len(self.requirements))
        # Sink demand represents the target number of requirements to fulfill
        G.add_node('sink', demand=len(self.requirements))

        # For each requirement, create a loading node for each day in its allowed window
        loading_nodes = []
        for req_idx, req in enumerate(self.requirements):
            allowed_ldr = req.allowed_ldr if hasattr(req, 'allowed_ldr') and req.allowed_ldr else {}
            for start_day, end_day in allowed_ldr.items():
                for day in range(int(start_day), int(end_day) + 1):
                    deploy_node = (req.origin, day)
                    loading_node = (req.origin, day, 'loading', req_idx)
                    delivery_node = ('Refinery', day + 1 + self.routes[self._get_route_key(req.origin, 'Refinery')].time_travel if self._get_route_key(req.origin, 'Refinery') in self.routes else 3, 'delivery', req_idx)
                    G.add_node(deploy_node)
                    G.add_node(loading_node)
                    G.add_node(delivery_node)
                    # Capacity of deploy_vessel edge changed to 1, add cost
                    G.add_edge('source', deploy_node, action='deploy_vessel', capacity=1, cost=cost_per_deployed_vessel) 
                    G.add_edge(deploy_node, loading_node, action='enter_loading', capacity=MAX_VESSELS, cost=0) # Multiple vessels can enter loading area
                    G.add_edge(loading_node, delivery_node, action='requirement_flow', capacity=1, cost=0, req_idx=req_idx, req=req, loading_day=day)
                    G.add_edge(delivery_node, 'sink', action='deliver', capacity=1, cost=0, req_idx=req_idx, req=req)
                    loading_nodes.append((loading_node, req_idx, day, req.origin))

        # Add travel/wait edges between loading nodes at different terminals and days
        for i, (ln1, req_idx1, day1, origin1) in enumerate(loading_nodes):
            for j, (ln2, req_idx2, day2, origin2) in enumerate(loading_nodes):
                if i == j:
                    continue
                # Wait edge: allow staying at the same terminal to load another requirement on a later day
                if origin1 == origin2 and day2 > day1:
                    G.add_edge(ln1, ln2, action='wait', capacity=MAX_VESSELS, cost=0, wait_days=day2-day1)
                else:
                    # Get travel time between origin1 and origin2
                    route_key = self._get_route_key(origin1, origin2)
                    travel_time = self.routes[route_key].time_travel if route_key in self.routes else 3  # Default 3 days
                    # Vessel can move from ln1 to ln2 if ln2's loading day is after ln1's loading day + 1 (loading) + travel_time
                    earliest_arrival = day1 + 1 + travel_time
                    if earliest_arrival <= day2:
                        G.add_edge(ln1, ln2, action='travel', capacity=MAX_VESSELS, cost=0, travel_days=travel_time)
        return G
    
    def _extract_solution_from_flow(self, network: nx.DiGraph, flow_dict: Dict, horizon_days: int) -> List[Vessel]:
        """Extract vessels and their routes with co-loading optimization and tolerance"""
        vessels = []
        active_vessels = {}
        vessel_counter = 0
        req_vessel_map = {} # Tracks which requirement is handled by which vessel_id
        
        # Create a mutable copy of flow_dict to track remaining flow
        remaining_flow_dict = copy.deepcopy(flow_dict)

        # Find all vessel deployments (from 'source' to deploy_node)
        source_flows = remaining_flow_dict.get('source', {})
        deployment_edges = []
        for v, flow_val in source_flows.items():
            if flow_val <= 0:
                continue
            edge_data = network.get_edge_data('source', v)
            if not edge_data:
                continue
            action = edge_data.get('action')
            if action and action.startswith('deploy_vessel'):
                deployment_edges.append({'node': v, 'flow': flow_val, 'action': action})

        # Sort deployment_edges to process them in a consistent order (e.g., by node name, then day)
        # This helps in making the vessel_id assignment more deterministic if needed.
        deployment_edges.sort(key=lambda x: (x['node'][0] if isinstance(x['node'], tuple) else str(x['node']), 
                                             x['node'][1] if isinstance(x['node'], tuple) and len(x['node']) > 1 else 0))

        for dep_edge in deployment_edges:
            v = dep_edge['node']
            # The flow_val on ('source', v) indicates how many vessels *can* start this way.
            # We will consume this flow as we deploy vessels.
            
            num_vessels_to_deploy_on_this_edge = int(remaining_flow_dict.get('source', {}).get(v, 0))

            for _ in range(num_vessels_to_deploy_on_this_edge):
                if remaining_flow_dict.get('source', {}).get(v, 0) < 1:
                    break # No more flow available on this deployment edge

                vessel_id = f"Vessel_{vessel_counter}"
                vessel_counter += 1
                largest_vessel_type = max(self.vessel_types, key=lambda x: x["capacity"])
                vessel = Vessel(
                    vessel_id=vessel_id,
                    capacity=largest_vessel_type["capacity"],
                    cost=largest_vessel_type["cost"],
                    arrival_day=0,
                    cargo=[],
                    days_held=0
                )
                vessel.route = []
                
                # Decrement flow from source to this deployment node
                remaining_flow_dict['source'][v] -= 1
                
                active_vessels[vessel_id] = {
                    'vessel': vessel,
                    'current_node': v, # Starting node for this vessel
                    'current_day': v[1] if isinstance(v, tuple) and len(v) > 1 else 0,
                    'grades': set(),
                    'capacity_used': 0,
                    'path': [],
                }
                location = v[0] if isinstance(v, tuple) else str(v)
                print(f"Created vessel {vessel_id} starting at {location} on day {active_vessels[vessel_id]['current_day']}")

        # For each vessel, traverse the flow path using remaining_flow_dict
        for vessel_id, vessel_info in active_vessels.items():
            print(f"\\n--- Vessel {vessel_id} route extraction ---")
            vessel = vessel_info['vessel']
            current_node = vessel_info['current_node']
            current_day = vessel_info['current_day']
            grades = vessel_info['grades']
            capacity_used = vessel_info['capacity_used']
            path = vessel_info['path']
            # cargo list is local to this vessel's path traversal
            current_cargo_list = [] 
            visited_nodes = set()

            while True:
                print(f"  Vessel {vessel_id}: At node: {current_node}, day: {current_day}, grades: {grades}, used: {capacity_used}/{vessel.capacity}")
                if current_node in visited_nodes and current_node != 'sink': # Allow sink to be "revisited" conceptually
                     # Check if it's a wait scenario; if current_node implies a time step, it's okay.
                     # For now, simple cycle break. More sophisticated needed if legitimate cycles exist.
                    print(f"    Vessel {vessel_id}: Detected loop or revisit to {current_node} without state change. Terminating path.")
                    break
                visited_nodes.add(current_node)

                req_idx_loaded_this_step = None # Reset for current step
                
                # Try to load if at a loading node
                if isinstance(current_node, tuple) and len(current_node) > 2 and 'loading' in current_node[2]: # e.g. (origin, day, 'loading', req_idx)
                    req_idx_at_node = current_node[3] # Assuming structure (loc, day, 'loading', req_idx)
                    
                    potential_load_edge = None
                    # Check if the specific requirement_flow edge for req_idx_at_node from current_node has flow
                    for _, out_v, out_data in network.out_edges(current_node, data=True):
                        if out_data.get('action') == 'requirement_flow' and out_data.get('req_idx') == req_idx_at_node:
                            if remaining_flow_dict.get(current_node, {}).get(out_v, 0) > 0:
                                potential_load_edge = {'u': current_node, 'v': out_v, 'data': out_data}
                                break
                    
                    if potential_load_edge:
                        req_to_load_data = potential_load_edge['data']
                        req_idx = req_to_load_data['req_idx']
                        requirement = req_to_load_data['req']
                        
                        print(f"    Vessel {vessel_id}: Considering requirement {req_idx}: grade={requirement.grade}, vol={requirement.volume}, origin={requirement.origin}")
                        if req_idx not in req_vessel_map:
                            if capacity_used + requirement.volume <= vessel.capacity:
                                new_grade = requirement.grade
                                can_add_grade = (new_grade in grades) or (len(grades) < 3)
                                if can_add_grade:
                                    req_vessel_map[req_idx] = vessel_id
                                    capacity_used += requirement.volume
                                    grades.add(new_grade)
                                    loading_day_val = current_node[1]
                                    
                                    parcel = FeedstockParcel(
                                        grade=requirement.grade,
                                        volume=requirement.volume,
                                        origin=requirement.origin,
                                        vessel_id=vessel_id, 
                                        ldr={loading_day_val: loading_day_val + 1} 
                                    )
                                    current_cargo_list.append(parcel)
                                    req_idx_loaded_this_step = req_idx # Set that a requirement was loaded in THIS step
                                    print(f"    LOADED: Req {req_idx} ({requirement.volume} of {requirement.grade}) by vessel {vessel_id} at {requirement.origin} on day {loading_day_val}")
                                else:
                                    print(f"    SKIP (Grade Limit): Cannot load req {req_idx} for vessel {vessel_id}. Grades: {grades}, New: {new_grade}")
                            else:
                                print(f"    SKIP (Capacity): Not enough capacity for requirement {req_idx} on vessel {vessel_id} (needed: {requirement.volume}, used: {capacity_used}, cap: {vessel.capacity})")
                        else:
                            print(f"    SKIP (Already Assigned): Requirement {req_idx} already assigned to {req_vessel_map[req_idx]}. Vessel {vessel_id} cannot load.")
                    else:
                        print(f"    Vessel {vessel_id}: At loading node {current_node} for req {req_idx_at_node}, but its requirement_flow edge has no remaining flow or doesn't exist.")

                # MOVED: Build next_node_options *before* deciding on FORCE MOVE or general move.
                next_node_options = []
                if current_node in remaining_flow_dict:
                    for out_v, flow_val in remaining_flow_dict[current_node].items():
                        if flow_val > 0:
                            edge_data = network.get_edge_data(current_node, out_v)
                            if edge_data:
                                action = edge_data.get('action')
                                
                                # CRITICAL FIX: Prevent empty vessel that did not just load from starting on a 'requirement_flow' path
                                if action == 'requirement_flow' and not current_cargo_list and req_idx_loaded_this_step is None:
                                    print(f"    Vessel {vessel_id} (empty at {current_node}, general move): Skipping 'requirement_flow' edge to {out_v} for req {edge_data.get('req_idx')} as it has no cargo and didn't just load.")
                                    continue 

                                next_node_options.append({
                                    'node': out_v,
                                    'action': action,
                                    'data': edge_data,
                                    'flow': flow_val 
                                })
                
                # Determine next move based on flow in remaining_flow_dict
                # This 'if/else' block was previously *before* populating next_node_options
                chosen_option = None # Initialize chosen_option
                if req_idx_loaded_this_step is not None:
                    # Force move along the loaded requirement's path
                    for option in next_node_options: # Now next_node_options is populated
                        if option['action'] == 'requirement_flow' and option['data'].get('req_idx') == req_idx_loaded_this_step:
                            chosen_option = option
                            print(f"    Vessel {vessel_id}: FORCE MOVE (loaded req {req_idx_loaded_this_step}), taking its 'requirement_flow' edge to {option['node']}")
                            break
                    if not chosen_option:
                        print(f"    CRITICAL ERROR: Vessel {vessel_id} loaded req {req_idx_loaded_this_step}, but its 'requirement_flow' edge from {current_node} has no remaining flow or not found. Options: {next_node_options}")
                        break 
                else:
                    # General move: Vessel did NOT load a requirement in this step.
                    # Build options for general moves (wait, travel, etc.)
                    # This part was effectively duplicated; next_node_options is already built above.
                    # The filtering for empty vessels on 'requirement_flow' is also done above.
                    
                    candidate_options_for_general_move = list(next_node_options) # Use the already populated and filtered options
                    action_preferences = ['wait', 'travel', 'enter_loading']
                    
                    if isinstance(current_node, tuple) and len(current_node) > 2 and 'delivery' in current_node[2]:
                        action_preferences.append('deliver')

                    for action_type_pref in action_preferences:
                        for option in candidate_options_for_general_move:
                            if option['action'] == action_type_pref:
                                chosen_option = option
                                print(f"    Vessel {vessel_id}: PREFERRED MOVE (General), taking '{chosen_option['action']}' edge to {chosen_option['node']}")
                                break 
                        if chosen_option:
                            break 
                    
                    if not chosen_option and candidate_options_for_general_move:
                        # If no preferred action, take any available that isn't 'requirement_flow' (already filtered for empty vessels)
                        # For vessels with cargo, 'requirement_flow' might be valid if it's to deliver its existing cargo.
                        # For now, if it's not a preferred action, and it's not a 'requirement_flow' for an empty vessel, it might be taken.
                        # The existing filter in next_node_options build handles the empty vessel case.
                        # If a vessel has cargo, it might take a 'requirement_flow' if it's the only option.
                        
                        # Let's be more explicit: if it's a general move, and the vessel has cargo, it should not take a NEW 'requirement_flow'
                        # unless it's to deliver its existing cargo.
                        # The current logic will pick the first from candidate_options_for_general_move if no preferred.
                        # This might include 'requirement_flow' if the vessel has cargo.
                        
                        # Simplification: if no preferred, take the first available from the already filtered list.
                        # The critical fix for empty vessels on 'requirement_flow' is done during next_node_options population.
                        chosen_option = candidate_options_for_general_move[0]
                        print(f"    Vessel {vessel_id}: FALLBACK (General Move), taking first available: {chosen_option['node']} via {chosen_option['action']}")
                                
                if not next_node_options and not chosen_option: # check next_node_options as well
                    print(f"  Vessel {vessel_id}: No further movement options with remaining flow from {current_node}.")
                    break
                
                if not chosen_option:
                    print(f"  Vessel {vessel_id}: Stuck at {current_node}. No valid next move found from available options with flow. Options considered: {next_node_options}")
                    break

                # Finalize move
                next_node = chosen_option['node']
                next_action = chosen_option['action']
                
                # Consume flow for the chosen edge
                remaining_flow_dict[current_node][next_node] -= 1
                
                print(f"  Vessel {vessel_id}: Moving from {current_node} to {next_node} (day {next_node[1] if isinstance(next_node, tuple) and len(next_node) > 1 else 'N/A'}) via {next_action}. Remaining flow on edge: {remaining_flow_dict[current_node][next_node]}")

                # Record path segment
                if isinstance(current_node, tuple) and isinstance(next_node, tuple) and len(current_node) > 0 and len(next_node) > 0:
                    from_loc = current_node[0]
                    to_loc = next_node[0]
                    action_day = next_node[1] if len(next_node) > 1 else current_day # Day of arrival at next_node

                    if next_action in ['travel', 'requirement_flow']:
                         # requirement_flow implies travel to refinery
                        travel_time = action_day - current_day
                        path.append({
                            "from": from_loc,
                            "to": to_loc,
                            "day_start_travel": current_day, # Day leaving current_node
                            "day_end_travel": action_day,     # Day arriving at next_node
                            "travel_days": travel_time,
                            "action": next_action
                        })
                        print(f"    LOGGED TRAVEL: {from_loc} (day {current_day}) -> {to_loc} (day {action_day}), action: {next_action}")
                    elif next_action == 'wait':
                         wait_days = action_day - current_day
                         path.append({
                            "from": from_loc,
                            "to": to_loc, # Should be same as from_loc
                            "day_start_wait": current_day,
                            "day_end_wait": action_day,
                            "wait_days": wait_days,
                            "action": 'wait'
                         })
                         print(f"    LOGGED WAIT: at {from_loc} from day {current_day} to day {action_day}")
                    # Other actions like 'enter_loading', 'deliver' are transitions, location might not change or changes implicitly.
                    # The 'day' update is key.

                current_node = next_node
                current_day = next_node[1] if isinstance(next_node, tuple) and len(next_node) > 1 else current_day
                
                # Update vessel_info for next iteration (though current_day, grades, capacity_used are local to this loop)
                vessel_info['current_day'] = current_day
                vessel_info['grades'] = grades # Persist grade changes
                vessel_info['capacity_used'] = capacity_used # Persist capacity changes


                if current_node == 'sink':
                     print(f"  Vessel {vessel_id} reached sink.")
                     break

            vessel.cargo = current_cargo_list # Assign collected cargo to the vessel object
            vessel.route = path
            if path and current_cargo_list: # Only consider vessels that moved and carried something
                # Calculate arrival_day at refinery based on the path
                refinery_arrival_days = [seg["day_end_travel"] for seg in path if seg["to"] == "Refinery" and seg["action"] in ['requirement_flow', 'travel']]
                if refinery_arrival_days:
                    vessel.arrival_day = max(refinery_arrival_days)
                elif path: # If no direct refinery arrival, take max day from path
                    all_days = []
                    for seg in path:
                        if "day_end_travel" in seg: all_days.append(seg["day_end_travel"])
                        if "day_end_wait" in seg: all_days.append(seg["day_end_wait"])
                    if all_days: vessel.arrival_day = max(all_days)
                    else: vessel.arrival_day = 0 # Fallback
                
                vessels.append(vessel) # Add to the list of scheduled vessels

        # Filter active_vessels to those that actually got cargo and a route
        # The `vessels` list is already built this way.
        
        # Print summary
        print(f"\\nFinal extracted vessels with cargo: {len(vessels)}")
        total_parcels_scheduled = sum(len(v.cargo) for v in vessels)
        total_volume_scheduled = sum(p.volume for v in vessels for p in v.cargo)
        
        if not self.requirements:
            print("No requirements to schedule.")
            fulfillment_percentage = 100.0
        elif sum(req.volume for req in self.requirements) == 0: # Avoid division by zero if total required volume is 0
            print("Total required volume is 0.")
            fulfillment_percentage = 100.0 if total_volume_scheduled == 0 else 0.0 # Or handle as appropriate
        else:
            total_required_volume = sum(req.volume for req in self.requirements)
            fulfillment_percentage = (total_volume_scheduled / total_required_volume * 100) if total_required_volume > 0 else 0.0

        print(f"Scheduled {total_parcels_scheduled} cargo parcels out of {len(self.requirements)} requirements.")
        print(f"Total scheduled volume: {total_volume_scheduled} ({fulfillment_percentage:.1f}% fulfilled).")

        # Print unfulfilled requirements
        unfulfilled_reqs = []
        for req_idx, req in enumerate(self.requirements):
            if req_idx not in req_vessel_map:
                unfulfilled_reqs.append(req)
                print(f"UNFULFILLED: Requirement {req_idx} (grade={req.grade}, vol={req.volume}, origin={req.origin}, allowed_ldr={getattr(req, 'allowed_ldr', None)})")
        
        if not unfulfilled_reqs:
            print("All requirements fulfilled!")
        else:
            print(f"\\n{len(unfulfilled_reqs)} Unfulfilled requirements details:")
            for req_idx, req in enumerate(self.requirements): # Iterate again to get original index for consistent printing
                if req_idx not in req_vessel_map:
                     print(f"  - Req {req_idx}: origin={req.origin}, grade={req.grade}, volume={req.volume}, allowed_ldr={getattr(req, 'allowed_ldr', None)}")

        return vessels
    
    # Keep the same helpers as before
    def optimize_and_save(self, horizon_days: int = 30,
                          cost_per_deployed_vessel: float = DEFAULT_COST_PER_DEPLOYED_VESSEL,
                          penalty_per_unmet_requirement: float = DEFAULT_PENALTY_PER_UNMET_REQUIREMENT) -> List[Vessel]:
        """Optimize and save results to JSON files"""
        vessels = self.optimize(horizon_days=horizon_days,
                                cost_per_deployed_vessel=cost_per_deployed_vessel,
                                penalty_per_unmet_requirement=penalty_per_unmet_requirement)
        
        # Convert to JSON format
        vessels_dict = {}
        vessel_routes = {}
        
        # Process each vessel and save to dictionaries
        for vessel in vessels:
            # Extract base location from vessel ID (Vessel_type_location_day)
            vessel_parts = vessel.vessel_id.split('_')
            if len(vessel_parts) >= 3:
                start_location = vessel_parts[2]  # Extract location from ID
            else:
                start_location = vessel.cargo[0].origin if vessel.cargo else "Peninsular Malaysia"
        
            # Convert to vessel dict format
            vessels_dict[vessel.vessel_id] = {
                "vessel_id": vessel.vessel_id,
                "arrival_day": vessel.arrival_day,
                "capacity": vessel.capacity,
                "cost": vessel.cost,
                "days_held": vessel.days_held,
                "cargo": [
                    {
                        "grade": cargo_item.grade,
                        "volume": cargo_item.volume,
                        "origin": cargo_item.origin,
                        "loading_start_day": next(iter(cargo_item.ldr.keys())) if hasattr(cargo_item, 'ldr') and cargo_item.ldr else 0,
                        "loading_end_day": next(iter(cargo_item.ldr.values())) if hasattr(cargo_item, 'ldr') and cargo_item.ldr else 0
                    }
                    for cargo_item in vessel.cargo
                ],
                "route": vessel.route if hasattr(vessel, "route") else []
            }
        
            # Generate day-by-day vessel routes
            days_dict = {}
            current_location = start_location  # Start at cargo's origin
            
            # Determine max_day from vessel.route segments
            max_day_in_route = 0
            if hasattr(vessel, "route") and vessel.route:
                for segment in vessel.route:
                    if "day_end_travel" in segment:
                        max_day_in_route = max(max_day_in_route, segment["day_end_travel"])
                    elif "day_end_wait" in segment:
                        max_day_in_route = max(max_day_in_route, segment["day_end_wait"])
            
            max_day = max(max_day_in_route, vessel.arrival_day)
        
            # Initialize vessel_routes entry
            vessel_routes[vessel.vessel_id] = {
                "start_location": start_location,
                "days": {}
            }
        
            # Create day-by-day location tracking
            days_dict = {}
            day = 0
        
            while day <= max_day:
                # Default to current location if no travel segment updates it
                current_day_location = current_location 

                if hasattr(vessel, "route") and vessel.route:
                    for route_segment in vessel.route:
                        action = route_segment.get("action")
                        if action in ["travel", "requirement_flow"]:
                            start_travel_day = route_segment.get("day_start_travel")
                            end_travel_day = route_segment.get("day_end_travel")
                            to_location = route_segment.get("to")
                            if start_travel_day is not None and end_travel_day is not None and to_location is not None:
                                if start_travel_day == day:
                                    current_day_location = f"en_route_to_{to_location}"
                                    current_location = f"en_route_to_{to_location}" # Persist for next days until arrival
                                    break # Found relevant segment for this day
                                elif start_travel_day < day < end_travel_day:
                                    current_day_location = f"en_route_to_{to_location}"
                                    # current_location is already set to en_route
                                    break # Found relevant segment for this day
                                elif end_travel_day == day:
                                    current_day_location = to_location
                                    current_location = to_location # Persist for next days until next travel
                                    break # Found relevant segment for this day
                        elif action == "wait":
                            start_wait_day = route_segment.get("day_start_wait")
                            end_wait_day = route_segment.get("day_end_wait")
                            wait_location = route_segment.get("from") # or to, should be same
                            if start_wait_day is not None and end_wait_day is not None and wait_location is not None:
                                if start_wait_day <= day < end_wait_day:
                                    current_day_location = wait_location
                                    current_location = wait_location # Persist during wait
                                    break # Found relevant segment for this day
                
                days_dict[str(day)] = current_day_location
                day += 1
        
            vessel_routes[vessel.vessel_id]["days"] = days_dict
    
        # Save to JSON files
        vessels_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dynamic_data", "vessels.json")
        routes_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "dynamic_data", "vessel_routes.json")
    
        with open(vessels_path, "w") as f:
            json.dump(vessels_dict, f, indent=2)
    
        with open(routes_path, "w") as f:
            json.dump(vessel_routes, f, indent=2)
    
        return vessels
        
    def _get_route_key(self, origin, destination):
        """Find the appropriate route key format that exists in the routes dictionary"""
        # Try various formats
        possible_keys = [
            f"{origin}_{destination}",
            f"{origin} to {destination}",
            f"{origin}-{destination}"
        ]
        
        for key in possible_keys:
            if key in self.routes:
                return key
        
        # If no exact match found, try case-insensitive matching
        for route_key in self.routes.keys():
            if origin.lower() in route_key.lower() and destination.lower() in route_key.lower():
                return route_key
        
        # Create a new key if not found
        new_key = f"{origin} to {destination}"
        default_travel_time = 3  # Default travel time
        
        self.routes[new_key] = Route(
            origin=origin,
            destination=destination,
            time_travel=default_travel_time,
            cost=10000  # Default cost
        )
        
        return new_key
    
    def visualize_solution(self, model, flow_vars, network):
        """Visualize the solution and provides detailed stats"""
        print("\n=== DETAILED SOLUTION ANALYSIS ===")
        
        # Collect all edges with positive flow
        active_edges = []
        for (u, v), var in flow_vars.items():
            if var.value() > 0:
                edge_data = network.get_edge_data(u, v)
                action = edge_data.get('action', 'unknown')
                cost = edge_data.get('cost', 0)
                capacity = edge_data.get('capacity', 0)
                req_idx = edge_data.get('req_idx', None)
                
                active_edges.append({
                    'from': u,
                    'to': v,
                    'flow': var.value(),
                    'action': action,
                    'cost': cost,
                    'capacity': capacity,
                    'req_idx': req_idx
                })
        
        # Count vessel deployments
        vessel_deployments = [e for e in active_edges 
                            if e['action'].startswith('deploy_vessel')]
        print(f"Total vessels deployed: {sum(e['flow'] for e in vessel_deployments)}")
        
        # Count regular vs penalty vessels
        regular = sum(e['flow'] for e in vessel_deployments if e['action'] == 'deploy_vessel')
        penalty = sum(e['flow'] for e in vessel_deployments if e['action'] != 'deploy_vessel')
        print(f"  - Regular vessels: {regular}")
        print(f"  - Penalty vessels: {penalty}")
        
        # Count requirements fulfilled
        req_fulfilled = [e for e in active_edges if e['action'] == 'deliver']
        print(f"Requirements fulfilled: {len(req_fulfilled)} of {len(self.requirements)}")
        
        # Calculate cost breakdown
        cost_by_action = {}
        for edge in active_edges:
            action = edge['action']
            cost = edge['cost'] * edge['flow']
            if action not in cost_by_action:
                cost_by_action[action] = 0
            cost_by_action[action] += cost
        
        print("\nCost breakdown:")
        for action, cost in sorted(cost_by_action.items(), key=lambda x: x[1], reverse=True):
            print(f"  {action}: {cost}")
        
        print(f"Total cost: {plp.value(model.objective)}")