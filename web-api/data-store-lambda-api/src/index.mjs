// This is designed to run as a Node.js based Lambda function within AWS
// The AWS API Gateway should point the following routings to this Lambda function:
// POST /items
// DELETE /items/{id}

// The foundation of this is based on Amazon's Lambda and DynamoDB tutorial:
// https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-dynamo-db.html

import { DynamoDBClient } from "@aws-sdk/client-dynamodb";
import {
  DynamoDBDocumentClient,
  PutCommand,
  GetCommand,
  DeleteCommand,
} from "@aws-sdk/lib-dynamodb";

// Connect to DynamoDB and to the "foot-imu-data" table
// Files are stored in the "foot-imu-data" with the 'file-name' as the ky
const client = new DynamoDBClient({});
const dynamo = DynamoDBDocumentClient.from(client);
const tableName = "foot-imu-data";

export const handler = async (event, context) => {
  let body;
  let statusCode = 200;
  const headers = {
    "Content-Type": "application/json",
  };

  try {
    // Route based on the request received
    switch (event.routeKey) {
      
      // Delete the file based on the file-name
      case "DELETE /items/{id}":
        await dynamo.send(
          new DeleteCommand({
            TableName: tableName,
            Key: {
              'file-name': event.pathParameters.id,
            },
          })
        );
        body = `Deleted item ${event.pathParameters.id}`;
        break;

      // We received a request to store a file
      case "POST /items":
        let requestJSON = JSON.parse(event.body);

        // Calculate the actual file start time based on the time in the request and the offset provided
        let file_start_time = Date.parse(requestJSON.current_time)
        file_start_time -= requestJSON.time_offset * 1000
        
        // Convert the data in the incoming request from quaternions to euler angles (pitch/roll/yaw)
        // This is more intuitive for the end user to analyze
        let newData = requestJSON.data;
        newData = newData.map(row => {
          let [time, quat_i, quat_j, quat_k, quat_real] = row;
          
          // Convert to euler angles (we only need pitch and roll in our analysis)
          // Yaw is based on how the user turns and isn't helpful for analyzing
          let pitch = Math.asin(2 * (quat_real * quat_j - quat_k * quat_i));
          let roll = Math.atan2(2 * (quat_real * quat_i + quat_j * quat_k), 1 - 2 * (quat_i * quat_i + quat_j * quat_j));

          // Convert from radians to degrees
          pitch *= 180 / Math.PI;
          roll *= 180 / Math.PI;

          // Return an array containing time, pitch, and roll limited to 3 decimal places (we have limited storage space in DynamoDB,
          // and three decimal places is accurate enough for our analysis
          return [Number(time.toFixed(3)), Number(roll.toFixed(3)), Number(pitch.toFixed(3))];
        });
        
        // Check to see if we've stored part of this file before - this will determine whether we need to
        // append this data to existing data in the database
        let existing = await dynamo.send(
          new GetCommand({
            TableName: tableName,
            Key: {
              'file-name': requestJSON.file_name,
            },
          })
        );

        // If we haven't store this file before, store it now
        if (!existing.Item) {
          await dynamo.send(
            new PutCommand({
              TableName: tableName,
              Item: {
                'start-time': file_start_time,
                'file-name': requestJSON.file_name,
                'data-points': requestJSON.data_points,
                'data': JSON.stringify(newData)
              },
            })
          );
          body = `Received file: ${requestJSON.file_name}, Number of elements: ${requestJSON.data_points}, Total number of elements: ${requestJSON.data_points}`;
        
        // If we've stored this file before, we need to append the current data to the existing data
        } else {
          let existing_data_points = existing.Item['data-points']
          let total_data_points = existing_data_points + requestJSON.data_points
          let existing_data = JSON.parse(existing.Item.data)
          let final_data = existing_data.concat(newData)
          await dynamo.send(
            new PutCommand({
              TableName: tableName,
              Item: {
                'start-time': file_start_time,
                'file-name': requestJSON.file_name,
                'data-points': total_data_points,
                'data': JSON.stringify(final_data)
              },
            })
          );
          body = `Received file: ${requestJSON.file_name}, Number of elements: ${requestJSON.data_points}, Total number of elements: ${total_data_points}`;
        }
        break;

      // Any other routes are unsupported
      default:
        console.log(event.body)
        throw new Error(`Unsupported route: "${event.routeKey}"`);
    }
  // If we enounter an error along the way, send an error status code/message back in the response
  } catch (err) {
    statusCode = 400;
    body = err.message;
  } finally {
    // Convert the body to json format before sending
    body = JSON.stringify(body);
  }

  // Send the response back to the device
  return {
    statusCode,
    body,
    headers,
  };
};