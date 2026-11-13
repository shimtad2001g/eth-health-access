api_version = 4

function setup()
  return {
    properties = {
      weight_name = 'routability',
      max_speed_for_map_matching = 120/3.6,
      use_turn_restrictions = true,
      left_hand_driving = false,
    },
    default_mode = mode.driving,
    default_speed = 30,
    oneway_handling = true,
    turn_penalty = 7.5,
    u_turn_penalty = 20,
  }
end

function process_way(profile, way, result)
  local highway = way:get_value_by_key("highway")
  if not highway then return end
  
  local speed = 30
  if highway == "motorway" or highway == "trunk" then speed = 90
  elseif highway == "primary" then speed = 70
  elseif highway == "secondary" then speed = 60
  elseif highway == "tertiary" then speed = 50
  elseif highway == "residential" or highway == "unclassified" then speed = 35
  elseif highway == "service" then speed = 20
  elseif highway == "track" then speed = 15
  end

  local surface = way:get_value_by_key("surface")
  if surface == "unpaved" or surface == "dirt" or surface == "earth" then
    speed = speed * 0.6
  end

  result.forward_speed = speed
  result.backward_speed = speed
  result.forward_mode = mode.driving
  result.backward_mode = mode.driving
  result.name = way:get_value_by_key("name")
  
  local oneway = way:get_value_by_key("oneway")
  if oneway == "yes" or oneway == "1" or oneway == "true" then
    result.backward_mode = mode.inaccessible
  elseif oneway == "-1" then
    result.forward_mode = mode.inaccessible
  end
end

function process_node(profile, node, result) end
function process_relation(profile, relation, way, result) end
function process_turn(profile, turn) end

return {
  setup = setup,
  process_way = process_way,
  process_node = process_node,
  process_relation = process_relation,
  process_turn = process_turn
}