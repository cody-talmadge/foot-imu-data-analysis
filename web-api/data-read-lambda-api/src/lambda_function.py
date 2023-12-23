# This is designed to run as a Python based Lambda function within AWS
# The AWS API Gateway should point the following routings to this Lambda function:
# GET /items
# GET /items/{id}

# This function is written in Python so that we can access the numpy and scipy libraries
# to do analysis on the data points before we send them to the web UI

import logging
import simplejson as json
import boto3
import numpy as np
import scipy
from scipy.interpolate import make_interp_spline
from scipy.signal import find_peaks
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Setup dynamodb to pull data from the foot-imu-data table
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('foot-imu-data')

def lambda_handler(event, context):
    logger.info("Event: " + json.dumps(event))
    method = event['routeKey'].split(" ")[0]
    path = event['routeKey'].split(" ")[1]

    # This function should only handle GET requests
    if method == 'GET':

        # If there's no ID in the path we return all items (files) in the table
        if path == '/items':
            file_list = table.scan(
                #Because there are hyphens in the column names, we need to use a ProjectionExpression
                ProjectionExpression='#fn, #st, #points',
                ExpressionAttributeNames={
                    '#fn': 'file-name',
                    '#st': 'start-time',
                    '#points': 'data-points'
                }
            )
            response = {
                'statusCode': 200,
                'body': json.dumps(file_list['Items'])
            }

        # If there is an ID in the path then we only return the requested item (file)
        elif path == "/items/{id}":
            file_name = event['pathParameters']['id']
            file_info = table.get_item(
                Key={'file-name': file_name}
            )

            # Return a 404 error if we can't find the requested item (file)
            if 'Item' not in file_info:
                response = {
                    'statusCode': 404,
                    'body': 'File not found'
                }
            else:
                try:
                    # Since the data for the file exists, we're going to do analysis on it before
                    # sending it to the web UI

                    # Read in the data and convert it into a numpy array that we can assess
                    ankle_data_raw = json.loads(file_info['Item']['data'])
                    logger.info(type(ankle_data_raw))
                    ankle_data = np.array(ankle_data_raw)
                    logger.info("Ankle Data:")
                    logger.info(type(ankle_data))
                    logger.info(ankle_data.shape)
                    time_data = ankle_data[:,0]
                    pitch_data = ankle_data[:,1]

                    # We need to convert the roll data for right feet so that steps can be
                    # compared between right and left feet (we want an outside roll to always
                    # have the same cardinality regardless of which foot it is)
                    if file_name[0:4] == "left":
                        roll_data = ankle_data[:,2]
                    else:
                        roll_data = -ankle_data[:,2]
                    
                    # Smooth out the pitch readings and then calculate the peaks and troughs in the pitch
                    # reading - we'll use these to calculate each step
                    smoothed_pitch = scipy.ndimage.gaussian_filter1d(pitch_data, sigma=2)
                    peaks, _ = find_peaks(pitch_data, prominence=1)
                    troughs, _ = find_peaks(-pitch_data, prominence=1)
                    
                    # Create an array of points that includes the index of each peak/trough and whether it is a peak or trough
                    points = [[int(time), "peak"] for time in peaks]
                    points += [[int(time), "trough"] for time in troughs]
                    # Sort this by index of the peak/trough
                    points.sort(key=lambda x:x[0])
                    
                    steps = []
                    step_times = []
                    step_values = []
                    total_step_times = []
                    foot_down_times = []
                    pitch_max = []
                    pitch_min = []
                    roll_max = []
                    roll_min = []
                    roll_values = []
                    
                    # We'll review the points to find steps
                    for i in range(len(points) - 2):
                        # We'll only consider steps as starting at a peak (this makes the analysis easier)
                        if points[i][1] == "trough":
                            continue

                        # We're going to determine steps by looking at the next three points
                        point_num, point_type = points[i]
                        point_time = time_data[point_num]
                        point_value = pitch_data[point_num]
    
                        next_num, next_type = points[i + 1]
                        next_time = time_data[next_num]
                        next_value = pitch_data[next_num]
    
                        two_num, two_type = points[i + 2]
                        two_time = time_data[two_num]
                        two_value = pitch_data[two_num]
    
                        # We'll define a steps as a peak-trough-peak pattern - if any of these are not met then skip
                        # to the next point
                        if point_type == "trough" or next_type == "peak" or two_type == "trough":
                            continue
    
                        # The peak pitch must be >= 5 degrees and the trough pitch must be <= -50 degrees to be considered a step
                        # This was determined imperically
                        if point_value < 5 or next_value > -50 or two_value < 5:
                            continue
    
                        # Check if the step is between 2 second and 0.5 seconds
                        # Note - here step actually refers to two steps since we're only looking at data from one leg
                        # This means that we're making sure the user is walking between 60 and 240 spm
                        # Anything not in this range we won't consider a step (it's too inconcistent to get good data out of)
                        step_time = two_time - point_time
                        #The time was too fast or short to be a step
                        if step_time > 2 or step_time < 0.5:
                            continue
    
                        #Now we know it's a step!

                        # Find and store the total time for the step, and the amount of time the foot was down
                        # We're assuming that the foot is down between the peak and trough of the pitch

                        # During the step your foot's pitch goes from it's maximum angle (when you start the step)
                        # to it's minimum angle (when your foot leaves the ground and the step-off happens)
                        steps.append((point_num, two_num))
                        total_step_times.append(step_time)
                        foot_down_times.append(next_time - point_time)
    
                        # Find and store the max/min roll angle for this step
                        roll_max.append(np.max(roll_data[point_num:two_num]))
                        roll_min.append(np.min(roll_data[point_num:two_num]))
    
                        # Find and store the max/min pitch angle for this step
                        pitch_max.append(point_value)
                        pitch_min.append(next_value)
    
                        # Store the pitch, roll, and time data for this step - we're later going to use this to calculate the "average" step
                        step_values.append(pitch_data[point_num:two_num+1])
                        roll_values.append(roll_data[point_num:two_num+1])
                        step_times.append(time_data[point_num:two_num+1])
                    
                    # Once we've found all of the steps, in the response object add information for the step count, average step time, etc.
                    # that we calculated above
                    response_body = file_info['Item']
                    response_body['step_count'] = len(total_step_times)
                    response_body['step_time_average'] = round(np.mean(total_step_times),2)
                    response_body['step_time_std_dev'] = round(np.std(total_step_times),2)
                    response_body['foot_down_time_average'] = round(np.mean(foot_down_times),2)
                    response_body['foot_down_time_std_dev'] = round(np.std(foot_down_times),2)
                    response_body['percent_time_foot_down'] = round(np.mean(foot_down_times) / np.mean(total_step_times) * 100, 1)
                    response_body['average_pitch_range'] = [round(np.mean(pitch_max), 1), round(np.mean(pitch_min), 1)]
                    response_body['average_roll_range'] = [round(np.mean(roll_max), 1), round(np.mean(roll_min), 1)]
                    
                    # We're going to break each step down into 20 pieces and then calculate the average pitch/roll across all steps
                    # for each of those pieces.  This will allow us to later graph the average across all steps
                    average_number_of_pieces = 20
                    # We create empty lists to store the average pitch and roll data
                    pitch_average = [[] for _ in range(average_number_of_pieces)]
                    roll_average = [[] for _ in range(average_number_of_pieces)]
                    # Calculate the start time for each of these 20 pieces (based on splitting the average step time into 30 intervals)
                    pitch_average_time = [i * np.mean(total_step_times) / (average_number_of_pieces - 1) for i in range(average_number_of_pieces)]

                    # Go through each point of each step and put it into the appropriate interval bucket in pitch_average and roll_average
                    for i in range(len(step_values)):
                        start_step_time = step_times[i][0]
                        end_step_time = step_times[i][-1]
                        step_amount = (end_step_time - start_step_time) / (average_number_of_pieces - 1)
                        for j in range(len(step_values[i])):
                            curr_time = step_times[i][j] - start_step_time
                            list_element = int(curr_time / step_amount)
                            pitch_average[list_element].append(step_values[i][j])
                            roll_average[list_element].append(roll_values[i][j])
                    
                    # Calculate the average of all of the steps in each pitch_average and roll_average interval
                    for i in range(len(pitch_average)):
                        pitch_average[i] = sum(pitch_average[i]) / len(pitch_average[i])
                        roll_average[i] = sum(roll_average[i]) / len(roll_average[i])
                    
                    # Since we're only using 30 points, build a spine using this data to display a smoothed version of the data to the user
                    Pitch_Spline = make_interp_spline(pitch_average_time, pitch_average)
                    Time_ = np.linspace(np.min(pitch_average_time), np.max(pitch_average_time), 500)
                    Pitch_ = Pitch_Spline(Time_)
                    Roll_Spline = make_interp_spline(pitch_average_time, roll_average)
                    Roll_ = Roll_Spline(Time_)
                    
                    logger.info(Time_)
                    logger.info(Roll_)
                    logger.info(Pitch_)
                    
                    # Include the spine for the average step time, roll, and pitch
                    response_body['average_step'] = {}
                    response_body['average_step']['time'] = list(Time_)
                    response_body['average_step']['roll'] = list(Roll_)
                    response_body['average_step']['pitch'] = list(Pitch_)
                    
                    # Do not include the raw data in the response (it's unnecessary now that we have data for the average step)
                    del(response_body['data'])
                    
                    logger.info(response_body)
                    
                    response = {
                        'statusCode': 200,
                        'body': json.dumps(response_body, ignore_nan=True)
                    }

                # If we get an error along the way there was likely an issue with the data (or no steps were identified)
                except:
                    response = {
                        'statusCode': 200,
                        'body': "Bad Data"
                    }
        else:
            # Send a 400 error if this lambda function doesn't handle the requested path
            response = {
                'statusCode': 400,
                'body': 'Bad Request'
            }
    else:
        # Send a 400 error if this lambda function doesn't handle the requested method
        response = {
            'statusCode': 400,
            'body': 'Bad Request'
        }
    
    #Send the response to the web UI
    response['headers'] = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*'
    }
    return response