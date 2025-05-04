-- Define a parameter table
local PARAM_TABLE_KEY = 77  -- Unique key for your parameter table (choose an unused value)
local PARAM_TABLE_PREFIX = "MY_"  -- Prefix for your parameter name

-- Add the parameter table to ArduPilot
assert(param:add_table(PARAM_TABLE_KEY, PARAM_TABLE_PREFIX, 1), "Could not add param table")

-- Add your custom parameter (ID 17 as an example value)
assert(param:add_param(PARAM_TABLE_KEY, 1, "PARAM", 17), "Could not add MY_PARAM")

-- Function to update periodically (example)
function update()
    local my_param = param:get("MY_PARAM")
    gcs:send_text(6, "MY_PARAM value: " .. tostring(my_param))
    return update, 1000  -- Run every 1000ms (1 second)
end

-- Start the script
return update, 1000