// This pulls in the analyzed data from the API and displays it to the user

// This is the AWS Gateway API URL
const apiUrlFileList = 'https://j88641zc71.execute-api.us-east-2.amazonaws.com/items';

let fileNameTable = document.getElementById('file-names');
let fileData = {}
let responseObj = {}

// Start by requesting all of the files that are available to analyze
fetch(apiUrlFileList)
.then(response => {
    return response.json();
})
.then(data => {
    console.log(data);

    // Sort the files by newewst file first
    data.sort((a,b) => b['start-time'] - a['start-time']);

    // Add each file to the "#file-names" table
    for (let file of data) {
        let fileName = file['file-name'];
        // Convert based on the local timezone (PST - hardcoded for now)
        let startTime = new Date(file['start-time'] + 1000 * 3600 * 8).toLocaleString();
        let dataPointCount = file['data-points']

        let tableRow = document.createElement("tr");
        let addRemoveCell = document.createElement("td");
        let fileNameCell = document.createElement("td");
        let startTimeCell = document.createElement("td");
        let dataPointCountCell = document.createElement("td");

        tableRow.setAttribute('id', `${fileName}-row`);
        addRemoveCell.setAttribute('class', 'plus');
        // This element is used to add/remove the file to the currently analyzed files
        addRemoveCell.innerHTML += `<strong><a href='#' id='${fileName}-add' onclick='addFile(this.id)'>+</a></strong>`;
        fileNameCell.innerHTML = fileName;
        startTimeCell.innerHTML = startTime;
        dataPointCountCell.innerHTML = dataPointCount;

        fileNameTable.appendChild(tableRow);
        tableRow.appendChild(addRemoveCell);
        tableRow.appendChild(fileNameCell);
        tableRow.appendChild(startTimeCell);
        tableRow.appendChild(dataPointCountCell);
    }

    responseObj = data;
});

// This function runs when the plus or minus icon next to a file is clicked
// If the "+" is clicked we should add the file to the list of files to analyze
// If the "-" is clicked we should remove the file from the list of files to analyze
function addFile(idName) {
    let addRemoveCell = document.getElementById(idName);
    // The id fro the <a> element has "-add" added to the file name so we need to remove it
    let fileName = idName.slice(0,-4);

    // We need to add the file to the list of files to analyze
    if (addRemoveCell.innerHTML == "+") {
        // Change the add button from a "+" to a "-" (ndash looks better visually than "-")
        addRemoveCell.innerHTML = "&ndash;";
        // Highlight the row in the file list to indiate it's being analyzed
        addRemoveRowId = idName.slice(0,-3) + "row";
        addRemoveRow = document.getElementById(addRemoveRowId);
        addRemoveRow.style.backgroundColor = "#FFFACD";

        // Get the info from the API
        let apiUrlFile = apiUrlFileList + "/" + fileName;
        fetch(apiUrlFile)
        .then(response => {
            return response.json();
        })
        .then(data => {
            fileData[fileName] = data;
            console.log(data)
            // Clear out the chart (we're going to rebuild it)
            document.getElementById("chart").innerHTML = "";
            if (Object.keys(fileData).length > 0) {
                let fileInfoTable = document.getElementById("file-info");
                // Build the file info table
                fileInfoTable.innerHTML = "";
                buildFileInfo();
                // Build the chart
                buildPlot();
            }
        });
    
    // We need to add the file to the list of files to analyze
    } else {
        // Change the add button from a "-" (ndash) to a "+"
        addRemoveCell.innerHTML = "+";
        // Un-highlight the row to indicate it is no longer being analyzed
        addRemoveRowId = idName.slice(0,-3) + "row";
        addRemoveRow = document.getElementById(addRemoveRowId);
        addRemoveRow.style.backgroundColor = "white";
        delete fileData[fileName];
        // Clear out the file info table (we're going to rebuild it)
        document.getElementById("chart").replaceChildren();
        let fileInfoTable = document.getElementById("file-info");
        fileInfoTable.innerHTML = "";
        if (Object.keys(fileData).length > 0) {
            // Build the file info table
            buildFileInfo();
            // Build the chart
            buildPlot();
        }
    }
}

function buildPlot() {

    //Set the margins for the chart
    let margin = {top: 20, right: 80, bottom: 30, left: 50},
        width = 700 - margin.left - margin.right,
        height = 380 - margin.top - margin.bottom;

    // The allData element contains the pitch and roll data for the average step from every selected file
    // It is used to build the y-axis to the right scale
    let allData = []
    // The allData elemetn contains the time data for the average step from every selected file
    // It is used to build the x-axis to the right scale
    let allTime = []
    for (let file of Object.keys(fileData)) {
        let data = fileData[file]['average_step'];
        allData = allData.concat(data.pitch);
        allData = allData.concat(data.roll);
        allTime = allTime.concat(data.time);
    }

    // Set the x-range based on the time data
    let x = d3.scaleLinear()
        .domain(d3.extent(allTime))
        .range([0, width]);
            
    // Set the y-range based on the pitch/roll data
    let y = d3.scaleLinear()
        .domain([
            d3.min(allData),
            d3.max(allData)
        ])
        .range([height, 0]);

    // Create a different color for pitch/roll and left/right
    var color = d3.scaleOrdinal(d3.schemeCategory10)
        .domain(["pitch-left", "roll-left", "pitch-right", "roll-right"]);

    // Create the x-axis with ticks 0.1 seconds apart
    var xAxis = d3.axisBottom()
        .scale(x)
        .tickFormat(d3.format('.1f'))

    // Create the y-axis
    var yAxis = d3.axisLeft()
        .scale(y)

    // Define how we're going to create the pitch lines (using the time as the x and the pitch as the y)
    var linePitch = d3.line()
    .curve(d3.curveBasis)
    .x(function(d) { return x(d.time); })
    .y(function(d) { return y(d.pitch); });

    // Define how we're going to create the roll lines (using the time as the x and the roll as the y)
    var lineRoll = d3.line()
    .curve(d3.curveBasis)
    .x(function(d) { return x(d.time); })
    .y(function(d) { return y(d.roll); });

    // Create the svg object and add the x and y axes
    var svg = d3.select("#chart").append("svg")
        .attr("width", width + margin.left + margin.right)
        .attr("height", height + margin.top + margin.bottom)
        .append("g")
        .attr("transform", "translate(" + margin.left + "," + margin.top + ")");
    svg.append("g")
        .attr("class", "x axis")
        .attr("transform", "translate(0," + height + ")")
        .call(xAxis);
    svg.append("g")
        .attr("class", "y axis")
        .call(yAxis);

    // Go through each file and add its pitch line and roll line to the chart
    for (let file of Object.keys(fileData)) {
        let data = fileData[file]['average_step'];
        // This mapping is required to get the data in the form that the line generators are expecting
        formattedData = data.time.map(function(time, i) {
            return {time: time, pitch: data.pitch[i], roll: data.roll[i]};
        });

        // Set the pitch and roll color depending on if this is a left or right foot
        // We want to be able to easily compare the difference between them
        let pitchColor;
        let rollColor;
        if (file.slice(0,4) == "left") {
            pitchColor = color("pitch-left");
            rollColor = color("roll-left");
        } else {
            pitchColor = color("pitch-right");
            rollColor = color("roll-right");
        }

        // Create the pitch line
        svg.append("path")
        .datum(formattedData)
        .attr("class", "line")
        .style("stroke", pitchColor)
        .attr("d", linePitch);
    
        // Create the roll line
        svg.append("path")
            .datum(formattedData)
            .attr("class", "line")
            .style("stroke", rollColor)
            .attr("d", lineRoll);
    }

    // Add legend data
    // From: https://d3-graph-gallery.com/graph/custom_legend.html
    svg.append("circle").attr("cx",500).attr("cy",260).attr("r", 6).style("fill", color("pitch-left"));
    svg.append("text").attr("x", 520).attr("y", 260).text("Left Pitch").style("font-size", "15px").attr("alignment-baseline","middle");
    svg.append("circle").attr("cx",500).attr("cy",280).attr("r", 6).style("fill", color("pitch-right"));
    svg.append("text").attr("x", 520).attr("y", 280).text("Right Pitch").style("font-size", "15px").attr("alignment-baseline","middle");
    svg.append("circle").attr("cx",500).attr("cy",300).attr("r", 6).style("fill", color("roll-left"));
    svg.append("text").attr("x", 520).attr("y", 300).text("Left Roll").style("font-size", "15px").attr("alignment-baseline","middle");
    svg.append("circle").attr("cx",500).attr("cy",320).attr("r", 6).style("fill", color("roll-right"));
    svg.append("text").attr("x", 520).attr("y", 320).text("Right Roll").style("font-size", "15px").attr("alignment-baseline","middle");

}

// Build the file info table
function buildFileInfo() {
    // The headers for the table (and the type of data that each row will include):
    tableHeaders = ["File Name", "Step Time", "Ground Time", "Ground %", "Step Pitch", "Step Roll"];
    let fileInfoTable = document.getElementById("file-info")
    fileInfoHeaderRow = document.createElement("tr");
    fileInfoTable.appendChild(fileInfoHeaderRow);
    
    // Create and append header titles
    for (let header of tableHeaders) {
        let headerCell = document.createElement("th");
        headerCell.innerHTML = header;
        fileInfoHeaderRow.appendChild(headerCell);
    }

    // Create and append data from each file
    for (let fileName of Object.keys(fileData)) {

        // Create the row element
        fileInfo = fileData[fileName]
        fileInfoDataRow = document.createElement("tr");
        fileInfoTable.appendChild(fileInfoDataRow);

        // Append the file name
        fileNameEl = document.createElement("td");
        fileNameEl.innerHTML = fileName;
        fileInfoDataRow.appendChild(fileNameEl);

        // Append the average and std-dev step time
        stepTime = document.createElement("td");
        stepTime.innerHTML = `${fileInfo.step_time_average.toFixed(2)}&plusmn;${fileInfo.step_time_std_dev.toFixed(2)}s`;
        fileInfoDataRow.appendChild(stepTime);

        // Append the average and std-dev foot down time
        footDownTime = document.createElement("td");
        footDownTime.innerHTML = `${fileInfo.foot_down_time_average.toFixed(2)}&plusmn;${fileInfo.foot_down_time_std_dev.toFixed(2)}s`;
        fileInfoDataRow.appendChild(footDownTime);

        // Append the average % of time the foot is down
        footDownPercent = document.createElement("td");
        footDownPercent.innerHTML = `${fileInfo.percent_time_foot_down.toFixed(1)}%`;
        fileInfoDataRow.appendChild(footDownPercent);

        // Append the average step pitch range
        footPitch = document.createElement("td");
        footPitch.innerHTML = `${fileInfo.average_pitch_range[1].toFixed(2)}&deg; - ${fileInfo.average_pitch_range[0].toFixed(2)}&deg;`;
        fileInfoDataRow.appendChild(footPitch);

        // Append the average step roll range
        footRoll = document.createElement("td");
        footRoll.innerHTML = `${fileInfo.average_roll_range[1].toFixed(2)}&deg; - ${fileInfo.average_roll_range[0].toFixed(2)}&deg;`;
        fileInfoDataRow.appendChild(footRoll);
    }

}