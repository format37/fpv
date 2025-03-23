-- Version 0.16
-- A script to list CSV files in the /LOGS/ directory and view GPS data with time in descending order

local fileList = {}      -- Table to store filenames
local fileCount = 0      -- Number of files
local startIndex = 1     -- First file to display
local selectedIndex = 1  -- Currently selected file
local maxVisible = 6     -- Maximum number of files visible at once

-- State management
local STATES = {
  FILE_LIST = 1,
  GPS_DATA = 2
}
local currentState = STATES.FILE_LIST
local gpsData = {}       -- To store the GPS coordinates with time
local gpsDataStartIndex = 1  -- For scrolling in GPS data view
local maxGpsVisible = 5  -- Maximum number of GPS entries visible at once

-- Function to check if a filename ends with .csv
local function hasCSVExtension(filename)
  local extension = string.lower(string.sub(filename, -4))  -- Get last 4 characters and convert to lowercase
  return extension == ".csv"
end

-- Simple bubble sort implementation that doesn't use the table library
local function sortFilesDescending(files, count)
  for i = 1, count do
    for j = 1, count - i do
      if files[j] < files[j + 1] then
        -- Swap files
        files[j], files[j + 1] = files[j + 1], files[j]
      end
    end
  end
end

-- Function to reverse array order (to sort GPS data in descending order)
local function reverseArray(arr)
  local n = #arr
  local temp
  for i = 1, math.floor(n/2) do
    -- Swap elements at positions i and n-i+1
    temp = arr[i]
    arr[i] = arr[n-i+1]
    arr[n-i+1] = temp
  end
  return arr
end

-- Function to load CSV files in directory
local function loadFiles()
  fileList = {}
  fileCount = 0
  for filename in dir("/LOGS") do
    -- Only add files with .csv extension
    if hasCSVExtension(filename) then
      fileCount = fileCount + 1
      fileList[fileCount] = filename
    end
  end
  
  -- Sort files in descending order (newer files first)
  if fileCount > 1 then
    sortFilesDescending(fileList, fileCount)
  end
  
  return fileCount
end

-- Function to read the selected CSV file and extract GPS data with time
local function loadGPSData(filename)
  gpsData = {}
  local gpsCount = 0
  local filePath = "/LOGS/" .. filename
  
  -- Try to read the file
  local f = io.open(filePath, "r")
  if not f then
    return 0  -- File not found or couldn't be opened
  end
  
  -- Read the entire file (for simplicity, we'll limit this approach to small files)
  local content = io.read(f, 20000)  -- Read up to 20KB
  io.close(f)
  
  if not content or content == "" then
    return 0  -- Empty file
  end
  
  -- Split content into lines
  local lines = {}
  for line in string.gmatch(content, "([^\n]+)") do
    lines[#lines + 1] = line
  end
  
  if #lines == 0 then
    return 0  -- No lines found
  end
  
  -- Parse header to find GPS and Time columns
  local headerLine = lines[1]
  local headers = {}
  local index = 1
  
  for field in string.gmatch(headerLine, "([^,]+)") do
    headers[index] = field
    index = index + 1
  end
  
  -- Find GPS column index (first occurrence)
  local gpsColumnIndex = 0
  local timeColumnIndex = 0
  for i = 1, #headers do
    if headers[i] == "GPS" and gpsColumnIndex == 0 then
      gpsColumnIndex = i
    end
    if headers[i] == "Time" then
      timeColumnIndex = i
    end
  end
  
  if gpsColumnIndex == 0 then
    return 0  -- GPS column not found
  end
  
  -- Process data lines
  for i = 2, math.min(27, #lines) do  -- Skip header, limit to 25 data rows
    local fields = {}
    local index = 1
    
    for field in string.gmatch(lines[i], "([^,]+)") do
      fields[index] = field
      index = index + 1
    end
    
    if #fields >= gpsColumnIndex then
      local gpsValue = fields[gpsColumnIndex]
      local timeValue = ""
      
      if timeColumnIndex > 0 and #fields >= timeColumnIndex then
        timeValue = fields[timeColumnIndex]
      end
      
      if gpsValue and gpsValue ~= "" then
        gpsCount = gpsCount + 1
        gpsData[gpsCount] = {
          time = timeValue,
          gps = gpsValue,
          rowIndex = i - 1  -- Store the original row index (0-based to match CSV rows)
        }
      end
    end
  end
  
  -- Reverse the array to get descending order (newest entries first)
  if gpsCount > 1 then
    gpsData = reverseArray(gpsData)
  end
  
  return gpsCount
end

-- Function to display GPS data with time
local function displayGPSData()
  lcd.clear()
  lcd.drawText(5, 0, "GPS from: " .. fileList[selectedIndex], SMLSIZE)
  
  if #gpsData == 0 then
    lcd.drawText(10, 25, "No GPS data found", 0)
  else
    -- Display GPS values with time
    local y = 12
    local displayCount = 0
    for i = gpsDataStartIndex, math.min(gpsDataStartIndex + maxGpsVisible - 1, #gpsData) do
      local entry = gpsData[i]
      -- local displayText = entry.rowIndex .. ": "  -- Use original row index
      local displayText = ""
      
      -- Add time prefix if available
      if entry.time and entry.time ~= "" then
        displayText = displayText .. entry.time .. " "
      end
      
      -- Add GPS data
      displayText = displayText .. entry.gps
      
      lcd.drawText(5, y, displayText, 0)
      y = y + 10
      displayCount = displayCount + 1
    end
    
    -- Draw scroll indicators if needed
    if gpsDataStartIndex > 1 then
      lcd.drawText(200, 12, "^", SMLSIZE)
    end
    if gpsDataStartIndex + maxGpsVisible - 1 < #gpsData then
      lcd.drawText(200, 55, "v", SMLSIZE)
    end
  end
  
end

local function run(event)
  if currentState == STATES.FILE_LIST then
    -- Load files on first run
    if fileCount == 0 then
      loadFiles()
    end
    
    -- Handle navigation events
    if event == EVT_VIRTUAL_NEXT or event == EVT_VIRTUAL_NEXT_REPT or event == EVT_ROT_RIGHT then
      -- Scroll down
      if selectedIndex < fileCount then
        selectedIndex = selectedIndex + 1
        -- If selected file would be off screen, scroll the view
        if selectedIndex > startIndex + maxVisible - 1 then
          startIndex = startIndex + 1
        end
      end
    elseif event == EVT_VIRTUAL_PREV or event == EVT_VIRTUAL_PREV_REPT or event == EVT_ROT_LEFT then
      -- Scroll up
      if selectedIndex > 1 then
        selectedIndex = selectedIndex - 1
        -- If selected file would be off screen, scroll the view
        if selectedIndex < startIndex then
          startIndex = startIndex - 1
        end
      end
    elseif event == EVT_VIRTUAL_ENTER or event == EVT_ENTER_BREAK then
      -- Switch to GPS data view
      if fileCount > 0 then
        local count = loadGPSData(fileList[selectedIndex])
        currentState = STATES.GPS_DATA
        gpsDataStartIndex = 1  -- Reset GPS data scroll position
      end
    elseif event == EVT_VIRTUAL_EXIT then
      return 1  -- Exit script
    end
    
    -- Draw file list
    lcd.clear()
    
    -- Draw scroll indicators if needed
    if startIndex > 1 then
      lcd.drawText(200, 2, "^", SMLSIZE)
    end
    if startIndex + maxVisible - 1 < fileCount then
      lcd.drawText(200, 55, "v", SMLSIZE)
    end
    
    -- Draw file list
    local y = 5
    for i = startIndex, math.min(startIndex + maxVisible - 1, fileCount) do
      -- Highlight selected item
      local flags = 0
      if i == selectedIndex then
        flags = INVERS
      end
      lcd.drawText(10, y, fileList[i], flags)
      y = y + 10
    end
    
  elseif currentState == STATES.GPS_DATA then
    -- Handle navigation in GPS data view
    if event == EVT_VIRTUAL_NEXT or event == EVT_VIRTUAL_NEXT_REPT or event == EVT_ROT_RIGHT then
      -- Scroll down
      if gpsDataStartIndex + maxGpsVisible - 1 < #gpsData then
        gpsDataStartIndex = gpsDataStartIndex + 1
      end
    elseif event == EVT_VIRTUAL_PREV or event == EVT_VIRTUAL_PREV_REPT or event == EVT_ROT_LEFT then
      -- Scroll up
      if gpsDataStartIndex > 1 then
        gpsDataStartIndex = gpsDataStartIndex - 1
      end
    elseif event == EVT_VIRTUAL_EXIT then
      -- Return to file list
      currentState = STATES.FILE_LIST
    end
    
    -- Display GPS data with time
    displayGPSData()
  end
  
  return 0
end

return { run = run }