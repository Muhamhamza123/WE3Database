# Import necessary libraries
from flask import Flask, request, jsonify, session
from flask_session import Session
import mysql.connector
from mysql.connector import pooling  # Added pooling module
from flask_cors import CORS
import csv
from datetime import datetime
from influxdb_client.client.write_api import WriteOptions, WritePrecision
from influxdb_client import InfluxDBClient, Point
import logging
import base64
import pandas as pd
from pandas import DataFrame
from datetime import datetime
import requests
from flask import Flask, request, jsonify, session, make_response
from flask_session import Session
from flask_cors import CORS
import mysql.connector
from mysql.connector import pooling
import jwt
from datetime import datetime, timedelta
from flask_jwt_extended import JWTManager, jwt_required, create_access_token
from mysql.connector import Error
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError


app = Flask(__name__)
CORS(app, supports_credentials=True, origins='http://localhost:3000')

# MySQL connection pooling configuration
mysql_pool = pooling.MySQLConnectionPool(
    pool_name="mysql_pool",
      pool_size=32,
     pool_reset_session=True,
     host="86.50.252.118",
     user="hamza",
     passwd="Nikon12345!",
     database="w3data-users",
     connect_timeout=10,
 )


# JWT configuration
app.config['SECRET_KEY'] = 'your_secret_key'
app.config['JWT_SECRET_KEY'] = 'your_jwt_secret_key'
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=15)
jwt = JWTManager(app)

# InfluxDB configuration
influxdb_url = 'http://86.50.252.118:8086'
influxdb_token = 'ynNB0w-RD65XSObOiDay0m1brg8Am14l2wFwB9ra2TYUN_6OFlaVGtStZD7S4bmJPJEri5Spmke22UKgw_qi_w=='
influxdb_org = 'w3data'
influxdb_bucket = "w3data"  # Update with your InfluxDB bucket

# InfluxDB connection pooling configuration
influxdb_pool = InfluxDBClient(
    url=influxdb_url,
    token=influxdb_token,
    org=influxdb_org
)

# Initialize the InfluxDB query API
query_api = influxdb_pool.query_api()
print("Connected to the databases")
# Function to get a MySQL connection from the pool
def get_mysql_connection():
    connection = mysql_pool.get_connection()
    return connection
# Function to close a MySQL connection
def close_mysql_connection(connection, cursor):
    try:
        if cursor:
            cursor.close()
            print("Cursor closed.")
        if connection:
            connection.close()
            print("Connection closed.")
    except Exception as e:
        logging.error("Error closing MySQL connection: %s", e)

def generate_token(username):
    payload = {
        'exp': datetime.utcnow() + timedelta(days=1),  # Token expiration time
        'iat': datetime.utcnow(),  # Token issue time
        'sub': username
    }
    token = jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')
    return token
def set_access_token_local_storage(response, access_token):
    response.headers['Authorization'] = f'Bearer {access_token}'
    response.headers['Access-Control-Expose-Headers'] = 'Authorization'  # Allow the client to access the Authorization header
@app.route('/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        # Respond to the preflight OPTIONS request
        response = make_response()
        response.headers['Access-Control-Allow-Origin'] = 'http://localhost:3000'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
        response.headers['Access-Control-Max-Age'] = '3600'
        return response
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    print(f"Received data: {data}")
    connection = mysql_pool.get_connection()
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT username FROM users WHERE username=%s AND password_hash=%s", (username, password))
        user = cursor.fetchone()
        if user:
            stored_username = user[0]
            access_token = create_access_token(identity=stored_username)
            response = jsonify(success=True, token=access_token)
            set_access_token_local_storage(response, access_token)
            close_mysql_connection(connection, cursor)
            print(f"User {stored_username} has logged in. Token: {access_token}")
            return response, 200  # 200 OK
        else:            
            close_mysql_connection(connection, cursor)
            return jsonify(success=False, error='Invalid username or password'), 404  # 404 Not Found       

    except mysql.connector.Error as e:
        # Handle MySQL database errors
        close_mysql_connection(connection, cursor)        
        return jsonify(success=False, error=str(e)), 500
    except Exception as e:
        # Handle database errors appropriately
        close_mysql_connection(connection, cursor)
        return jsonify(success=False, error=str(e)), 500
# ... (previous code)
    
@app.route('/update_metadata', methods=['PUT'])
def update_metadata():
    data = request.get_json()
    if 'selectedProject' not in data or 'version' not in data or 'editedMetadata' not in data:
        return jsonify({'error': 'Invalid request'}), 400
    projectname = data['selectedProject']
    version = data['version']
    edited_metadata = data['editedMetadata']
    # Print statement to log the 'version' value
    print(f"Received version: {version}")
    print(projectname)
    print(edited_metadata)
    connection = mysql_pool.get_connection()
    cursor = connection.cursor()
    if connection:
        try:
            cursor = connection.cursor(dictionary=True)
            # Retrieve project_id based on projectname
            cursor.execute("SELECT project_id FROM projects WHERE project_name = %s", (projectname,))
            project_result = cursor.fetchone()
            if project_result:
                project_id = project_result['project_id']
                # Retrieve existing metadata
                cursor.execute("SELECT * FROM `project_metadata` WHERE `project_id` = %s AND `version` = %s", (project_id, version))
                existing_metadata = cursor.fetchone()
                if existing_metadata:
                    # Build the UPDATE query dynamically based on changed fields
                    update_query = "UPDATE `project_metadata` SET "
                    updates = []
                    for key, value in edited_metadata.items():
                        # Check if the field has changed
                        if existing_metadata.get(key) != value:
                            updates.append(f"`{key}` = %s")
                    if updates:
                        update_query += ', '.join(updates)
                        update_query += " WHERE `project_id` = %s AND `version` = %s"

                        # Create a tuple of values to be substituted in the query
                        update_values = [edited_metadata[key] for key in edited_metadata if existing_metadata.get(key) != edited_metadata[key]]
                        update_values.extend([project_id, version])

                        # Print the SQL query for debugging
                        print("SQL Query:", update_query % tuple(update_values))

                        cursor.execute(update_query, update_values)
                        connection.commit()

                        return jsonify({'message': 'Metadata updated successfully'}), 200
                    else:
                        return jsonify({'message': 'No changes to update'}), 200

                else:
                    return jsonify({'error': 'Record not found'}), 404

            else:
                return jsonify({'error': 'Project not found'}), 404

        except Error as e:
            print(f"Error: {e}")
            return jsonify({'error': 'Internal server error'}), 500

        finally:
            if connection.is_connected():
                cursor.close()
                connection.close()








# Function to get an InfluxDB connection from the pool
def get_influxdb_connection():
    return influxdb_pool
# Function to close an InfluxDB connection


def get_project_metadata(cursor, project_ids,connection):
    try:
        cursor = connection.cursor(dictionary=True)
        # Format the project IDs as a string for the SQL query
        project_ids_str = ",".join(map(str, project_ids))
        # Get the column names from the table
        cursor.execute(f"DESCRIBE project_metadata")
        column_names = [row[0] for row in cursor.fetchall()]
        # Build the SELECT statement with all column names
        select_statement = f"SELECT {', '.join(column_names)} FROM project_metadata"
        # Add the WHERE clause to filter by project IDs
        select_statement += f" WHERE project_id IN ({project_ids_str})"
        cursor.execute(select_statement)
        # Map the result to a list of dictionaries with field names as keys
        metadata = [dict(zip(column_names, row)) for row in cursor.fetchall()]
        print("Metadata:", metadata)
        return metadata
    except Exception as e:
        print("Error fetching metadata:", e)
        return []
    finally:
            if connection.is_connected():
                cursor.close()
                connection.close()

@app.route('/user-projects/<username>', methods=['GET'])
def fetch_user_projects(username):
    connection = get_mysql_connection()
    cursor = connection.cursor()

    if username:
        cursor.execute("SELECT user_id FROM users WHERE username = %s", (username,))
        user_row = cursor.fetchone()
        if user_row:
            user_id = user_row[0]
            cursor.execute("""
                SELECT projects.project_id, projects.project_name, projects.description
                FROM projects
                JOIN user_projects ON projects.project_id = user_projects.project_id
                WHERE user_projects.user_id = %s
            """, (user_id,))

            projects_data = cursor.fetchall()
            projects = [{'project_id': row[0], 'project_name': row[1], 'project_description': row[2]} for row in projects_data]
            
            # Include the following code to get metadata
            try:
                project_ids_str = ",".join(map(str, [row[0] for row in projects_data]))
                cursor.execute(f"DESCRIBE project_metadata")
                column_names = [row[0] for row in cursor.fetchall()]
                select_statement = f"SELECT {', '.join(column_names)} FROM project_metadata"
                select_statement += f" WHERE project_id IN ({project_ids_str})"
                cursor.execute(select_statement)
                metadata = [dict(zip(column_names, row)) for row in cursor.fetchall()]
                # Combine project information with metadata
                for project in projects:
                    project_metadata = next((meta for meta in metadata if meta['project_id'] == project['project_id']), {})
                    project.update(project_metadata)                  

                return jsonify({
                    'projects': projects,
                    'project_count': len(projects),
                    'metadata': metadata
                })

            except Exception as e:
                print("Error fetching metadata:", e)
                return jsonify({
                    'projects': [],
                    'project_count': 0,
                    'metadata': []
                })

    close_mysql_connection(connection, cursor)
    return jsonify({
        'projects': [],
        'project_count': 0,
        'metadata': []
    })
    

def fetch_and_format_influx_data(username, measurement_name, project_name):
    client = get_influxdb_connection()
    query = f'''
            from(bucket: "{influxdb_bucket}")
            |> range(start: -3000d)
            |> filter(fn: (r) => r["_measurement"] == "{measurement_name}") 
            |> filter(fn: (r) => r["data_creator"] ==  "{username}")            
    '''
    if project_name:
      query += f'|> filter(fn: (r) => r["project_name"] == "{project_name}")'
    tables = client.query_api().query(query)
    data_list = []

    field_names = set()  # Initialize a set to store all field names

    for table in tables:
        for record in table.records:
            time = record.get_time()
            field = record.get_field()
            value = record.get_value()
            field_names.add(field)  # Add each field to the set of field names

            data_list.append({
                'Time': time.isoformat(),
                'Field': field,
                'Value': value,
            })         

    
    return {
        'data_list': data_list,
        'field_names': list(field_names),  # Convert the set of field names to a list
    }

# Route to fetch InfluxDB data with a measurement name
@app.route('/influxdb-data/<username>', methods=['GET'])
def get_influxdb_data(username):
    measurement_name = request.args.get('measurement')  # Get the measurement name from the query parameter
    project_name = request.args.get('project')    
    # Print the selected measurement name
    print(f"Selected Measurement Name: {measurement_name}")
    print(f"Selected Project Name: {project_name}")
    data = fetch_and_format_influx_data(username, measurement_name, project_name)
    return jsonify(data)

# Route to fetch measurement names from InfluxDB
@app.route('/measurements', methods=['GET'])
def get_measurements():
    client = get_influxdb_connection()
    measurements = []
    flux_query = f'import "influxdata/influxdb/schema"\nschema.measurements(bucket: "{influxdb_bucket}", start: -1000d, stop: now())'
    result = query_api.query(flux_query)
    for table in result:
        for record in table.records:
            measurements.append(record.get_value())

   
    return jsonify(measurements)

@app.route('/fields', methods=['GET'])
def get_fields():
    try:
        measurement = request.args.get('measurement')
        if not measurement:
            return jsonify({'error': 'Measurement not provided'}), 400

        # Use InfluxDB to fetch fields for the selected measurement
        fields = []
        flux_query = f'import "influxdata/influxdb/schema"\nschema.fieldKeys(bucket: "{influxdb_bucket}", predicate: (r) => r._measurement == "{measurement}", start: -10000d, stop: now())'

        try:
            result = query_api.query(flux_query)
        except Exception as e:
            return jsonify({'error': f'Error querying fields from InfluxDB: {str(e)}'}), 500

        for table in result:
            for record in table.records:
                fields.append(record.get_value())

        return jsonify(fields)

    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500
    



# Route to fetch InfluxDB data with a measurement name
@app.route('/influxdb-data-home/<username>', methods=['GET'])
def get_influxdb_data_home(username):
      # Get the measurement name from the query parameter    
    # Print the selected measurement name
    
    data = fetch_and_format_influx_data_home(username)
    return jsonify(data)
    
def fetch_and_format_influx_data_home(username):
    client = get_influxdb_connection()
    query = f'''
            from(bucket: "{influxdb_bucket}")
            |> range(start: 2000-01-01T00:00:00Z)
            |> filter(fn: (r) => r["data_creator"] ==  "{username}")
            
    '''
    tables = client.query_api().query(query)
    data_list = []
    field_names = set()  # Initialize a set to store all field names
    for table in tables:
        for record in table.records:
            time = record.get_time()
            field = record.get_field()
            value = record.get_value()
            field_names.add(field)  # Add each field to the set of field names
            data_list.append({
                'Time': time.isoformat(),
                'Field': field,
                'Value': value,
            })          

    
    return {
        'data_list': data_list,
        'field_names': list(field_names),  # Convert the set of field names to a list
    }


@app.route('/update-project', methods=['PUT'])
def update_project():
    data = request.get_json()
    new_project_name = data.get('project_name')
    new_project_description = data.get('project_description')
    connection = get_mysql_connection()
    cursor = connection.cursor()
    
    try:
        cursor.execute("UPDATE projects SET description = %s WHERE project_name = %s", (new_project_description, new_project_name))
        connection.commit()
        return jsonify(success=True, message="Project updated successfully")
    except mysql.connector.Error as err:
        return jsonify(success=False, message=f"Error updating project: {err}")
    finally:
        close_mysql_connection(connection, cursor)

@app.route('/profile/<username>', methods=['GET', 'PUT'])
def user_profile(username):
    try:
        # Check if the user is logged in (username is stored in the session)
        session_username = username

        # Ensure that the session username matches the parameter
        if session_username == username:
            if request.method == 'GET':
                connection = get_mysql_connection()
                cursor = connection.cursor()

                cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
                user_data = cursor.fetchone()
                if user_data:
                    user_profile = {
                        'user_id': user_data[0],
                        'username': user_data[1],
                        'email': user_data[4],
                        'profile_picture': base64.b64encode(user_data[5]).decode('utf-8'),
                        'firstname': user_data[6] if user_data[6] else None,
                        'lastname': user_data[7] if user_data[7] else None,
                        'Address': user_data[8] if user_data[8] else None,
                        'city': user_data[9] if user_data[9] else None,
                        'country': user_data[10] if user_data[10] else None,
                        'aboutme': user_data[11] if user_data[11] else None,
                        'teamname': user_data[12] if user_data[12] else None,

                        # Add other user-related fields as needed
                    }
                    close_mysql_connection(connection, cursor)
                    

                    return jsonify(user_profile)
                else:
                    return jsonify({'error': 'User not found'}), 404
            elif request.method == 'PUT':
                new_username = request.form.get('username')
                new_email = request.form.get('email')
                new_profile_picture = request.files.get('profile_picture')
                new_firstname = request.form.get('firstname')
                new_lastname = request.form.get('lastname')
                new_city = request.form.get('city')
                new_country = request.form.get('country')
                new_about_me = request.form.get('AboutMe')
                new_team_name = request.form.get('teamname')
                new_Adress = request.form.get('Address')

                connection = get_mysql_connection()
                cursor = connection.cursor()

                try:
                    update_query = "UPDATE users SET"
                    update_values = []

                    if new_username:
                        update_query += " username=%s,"
                        update_values.append(new_username)
                    if new_email:
                        update_query += " email=%s,"
                        update_values.append(new_email)
                    if new_profile_picture:
                        update_query += " profile_picture=%s,"
                        update_values.append(new_profile_picture.read())
                    if new_firstname:
                        update_query += " firstname=%s,"
                        update_values.append(new_firstname)
                    if new_lastname:
                        update_query += " lastname=%s,"
                        update_values.append(new_lastname)
                    if new_city:
                        update_query += " city=%s,"
                        update_values.append(new_city)
                    if new_country:
                        update_query += " country=%s,"
                        update_values.append(new_country)
                    if new_about_me:
                        update_query += " AboutMe=%s,"
                        update_values.append(new_about_me)
                    if new_team_name:
                        update_query += " teamname=%s,"
                        update_values.append(new_team_name)
                    if new_Adress:
                        update_query += " Address=%s,"
                        update_values.append(new_Adress)

                    update_query = update_query.rstrip(',')
                    update_query += " WHERE username=%s"
                    update_values.append(username)

                    cursor.execute(update_query, tuple(update_values))
                    connection.commit()
                    close_mysql_connection(connection, cursor)
                    print("MySQL connection closed.")

                    return jsonify({'message': 'User profile updated successfully'})
                except Exception as e:
                    print(f"Error updating user profile: {e}")
                    connection.rollback()
                   
                    return jsonify({'error': 'Internal Server Error'}), 500
        else:
            return jsonify({'error': 'Unauthorized - Session username does not match the route parameter'}), 401
    except Exception as e:
        print(f"Error fetching/updating user profile: {e}")
        return jsonify({'error': 'Internal Server Error'}), 500




############################################################################################################################################################################################################################################################
############################################################################################################################################################################################################################################################
############################################################################################################################################################################################################################################################



#query_api = influxdb_pool.query_api()

# InfluxDB Write API endpoint
write_api = influxdb_pool.write_api(write_options=WriteOptions(batch_size=50000, flush_interval=10_000))


def parse_row(row):
    timestamp_str = f'{row[0]} {row[1]}'
    try:
        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        return timestamp
    except ValueError:
        print(f"Failed to parse timestamp: {timestamp_str}")
        return None


# Route for handling file uploads
@app.route('/upload', methods=['POST'])
def upload_data():
    if 'file' not in request.files:
        return jsonify({'message': 'No file part'})

    file = request.files['file']

    if file.filename == '':
        return jsonify({'message': 'No selected file'})

    data_creator = request.form['dataCreator']
    project_name = request.form['projectName']
    location = request.form['location']
    date_generated = request.form['dateGenerated']
    selected_measurement = request.form['selectedMeasurement']

    if file:
        file.save(file.filename)
        process_result = process_csv(file.filename, data_creator, project_name, location, date_generated, selected_measurement)

        # Check if the CSV processing was successful
        if process_result['success']:
            print(f"Inserting data into MySQL for project: {project_name}")
            result = submit_metadata(request.form, project_name, location, selected_measurement)  # Pass project_name to the function
            print(f"submit_metadata result: {result}")
            if result:
                return result
            return jsonify({'message': 'Data uploaded successfully'})
        else:
            return jsonify({'message': f'CSV processing failed: {process_result["error"]}'})
    return jsonify({'message': 'File upload failed'})

def process_csv(file_path, data_creator, project_name, location, date_generated, selected_measurement):
    data_points = []  # List to collect data points before writing in chunks

    try:
        with open(file_path, 'r') as file:
            csv_reader = csv.reader(file, delimiter=';')  # Update delimiter if needed

            header = next(csv_reader)
            if "Date" in header and "Time" not in header:
                date_index = header.index("Date")

                for row_number, row in enumerate(csv_reader, start=2):  # Start at 2 to account for header
                    if len(row) < len(header):
                        row += [None] * (len(header) - len(row))

                    date_str = row[date_index].strip()
                    timestamp_str = f"{date_str}"

                    # Choose timestamp format based on the presence of dot
                    try:
                        timestamp_format = '%Y-%m-%d' if '.' not in timestamp_str else '%Y-%m-%d %H:%M:%S.%f'
                        timestamp = datetime.strptime(timestamp_str, timestamp_format)
                    except ValueError:
                        error_msg = f"Error parsing timestamp at line {row_number}: {timestamp_str}"
                        print(error_msg)
                        return {'success': False, 'error': error_msg}

                    rfc3339_timestamp = timestamp.isoformat()

                    data_point = Point(selected_measurement)

                    # Add the new fields (Data Creator, Project Name, Location, and Date Generated)
                    data_point.tag("data_creator", data_creator)
                    data_point.tag("project_name", project_name)
                    data_point.tag("location", location)
                    data_point.tag("date_generated", date_generated)

                    for i, field_name in enumerate(header):
                        if field_name == "Date":
                            continue  # Skip Date column

                        # Check for "NA" or empty values
                        if row[i] in ["NA", ""]:
                            value = None  # Represent null value
                        else:
                            # Attempt to convert the value to float, if it fails, treat it as a string
                            try:
                                value = float(row[i])
                            except (ValueError, TypeError):
                                value = row[i]

                        data_point.field(field_name, value)

                    data_point.time(rfc3339_timestamp, WritePrecision.NS)

                    # Append the data point to the list
                    data_points.append(data_point)

                    # Check if the number of data points reaches the batch size
                    if len(data_points) == 50000:
                        # Write data points in chunks
                        write_data_points(data_points)
                        data_points = []
    
    
                

            elif "Date" in header and "Time" in header:
                date_index = header.index("Date")
                time_index = header.index("Time")

                for row_number, row in enumerate(csv_reader, start=2):  # Start at 2 to account for header
                    if len(row) < 5:
                        row += [None] * (5 - len(row))

                    date_str = row[date_index].strip()
                    time_str = row[time_index].strip()
                    timestamp_str = f"{date_str} {time_str}"

    # Choose timestamp format based on the presence of dot
                   

                    try:
                        timestamp_format = '%Y-%m-%d %H:%M:%S.%f' if '.' in timestamp_str else '%Y-%m-%d %H:%M:%S'
                        timestamp = datetime.strptime(timestamp_str, timestamp_format)
                    except ValueError:
                        error_msg = f"Error parsing timestamp at line {row_number}: {timestamp_str}"
                        print(error_msg)
                        return {'success': False, 'error': error_msg}

                    rfc3339_timestamp = timestamp.isoformat()

                    data_point = Point("Pallas Stream Sensors")

                    # Add the new fields (Data Creator, Project Name, Location, and Date Generated)
                    data_point.tag("data_creator", data_creator)
                    data_point.tag("project_name", project_name)
                    data_point.tag("location", location)
                    data_point.tag("date_generated", date_generated)

                    for i, field_name in enumerate(header):
                        if field_name in ["Date", "Time"]:
                            continue  # Skip Date and Time columns

                        # Check for "NA" or empty values
                        if row[i] in ["NA", ""]:
                            value = None  # Represent null value
                        else:
                            try:                                
                                value = float(row[i])
                            except (ValueError, TypeError):
                                value = row[i]   
                                return {'success': False, 'error': error_msg}

                        data_point.field(field_name, value)

                    data_point.time(rfc3339_timestamp, WritePrecision.NS)

                    # Append the data point to the list
                    data_points.append(data_point)

                    # Check if the number of data points reaches the batch size
                    if len(data_points) == 50000:
                        # Write data points in chunks
                        write_data_points(data_points)
                        data_points = []

            elif "timestamp" in header:
                timestamp_index = header.index("timestamp")

                for row_number, row in enumerate(csv_reader, start=2):  # Start at 2 to account for header
                    if len(row) < 5:
                        row += [None] * (5 - len(row))

                    timestamp_str = row[timestamp_index].strip()  # Remove leading/trailing whitespace
                    timestamp_format = '%Y-%m-%d %H:%M:%S.%f' if '.' in timestamp_str else '%Y-%m-%d %H:%M:%S'

                    try:
                        timestamp = datetime.strptime(timestamp_str, timestamp_format)
                    except ValueError:
                        error_msg = f"Error parsing timestamp at line {row_number}: {timestamp_str}"
                        print(error_msg)
                        return {'success': False, 'error': error_msg}

                    rfc3339_timestamp = timestamp.isoformat()

                    data_point = Point(selected_measurement)

                    # Add the new fields (Data Creator, Project Name, Location, and Date Generated)
                    data_point.tag("data_creator", data_creator)
                    data_point.tag("project_name", project_name)
                    data_point.tag("location", location)
                    data_point.tag("date_generated", date_generated)

                    for i, field_name in enumerate(header):
                        if field_name in ["timestamp"]:
                            continue  # Skip timestamp columns

                        # Check for "NA" or empty values
                        if row[i] in ["NA", ""]:
                            value = None  # Represent null value
                        else:
                            try:
                                value = float(row[i])
                            except (ValueError, TypeError):                               
                                value = row[i]   
                                return {'success': False, 'error': error_msg}  

                        data_point.field(field_name, value)

                    data_point.time(rfc3339_timestamp, WritePrecision.NS)

                    # Append the data point to the list
                    data_points.append(data_point)

                    # Check if the number of data points reaches the batch size
                    if len(data_points) == 50000:
                        # Write data points in chunks
                        write_data_points(data_points)
                        data_points = []  # Clear the list for the next batch

            else:
                error_msg = "File does not contain a suitable timestamp or date/time column."
                print(error_msg)
                return {'success': False, 'error': error_msg}

        # Write any remaining data points
        if data_points:
            write_data_points(data_points)

        return {'success': True}

    except Exception as e:
        error_msg = f"Failed to process CSV: {e}"
        print(error_msg)
        return {'success': False, 'error': error_msg}
    
def write_data_points(data_points):
    try:
        # Write the data points in chunks using InfluxDB Write API
        result = write_api.write(bucket=influxdb_bucket, org=influxdb_org, record=data_points)
        print(f"Data points written successfully: {len(data_points)}")
    except Exception as e:
        print(f"Failed to write data points. Error: {e}")
        # Roll back MySQL transaction
        mysql_pool.rollback()

from flask import jsonify  # Assuming you are using Flask for JSON responses

def submit_metadata(form_data, project_name, location, selected_measurement):
    abstract = form_data['abstract']
    data_owner = form_data['dataOwner']
    contact_email = form_data['contactEmail']
    orcid_id = form_data['orcidId']
    other_contributors = form_data['otherContributors']
    funding_information = form_data['fundingInformation']
    data_license = form_data['dataLicense']
    latitude = form_data['latitude']
    longitude = form_data['longitude']
    time_zone = form_data['timeZone']
    unit_of_measurement = form_data['unitOfMeasurement']
    sensor_make_and_type = form_data['sensorMakeAndType']
    sensor_accuracy = form_data['sensorAccuracy']
    sampling_method = form_data['samplingMethod']
    related_publication = form_data['relatedPublication']
    additional_notes = form_data['additionalNotes']

    print(project_name)

    try:
        check_project_query = 'SELECT project_id FROM projects WHERE project_name = %s LIMIT 1'
        connection = mysql_pool.get_connection()
        cursor = connection.cursor()
        cursor.execute(check_project_query, (project_name,))
        project_result = cursor.fetchone()

        if project_result:
            project_id = project_result[0]

            get_latest_version_query = '''
                SELECT version FROM project_metadata
                WHERE project_id = %s
                ORDER BY version DESC LIMIT 1
            '''

            cursor.execute(get_latest_version_query, (project_id,))
            version_result = cursor.fetchone()

            if version_result:
                raw_version = version_result[0]
                new_version = generate_version(location, longitude, latitude, selected_measurement, raw_version)

                print(f'Project ID: {project_id}, Latest Version: {raw_version}, New Version: {new_version}')

                insert_query = '''
                    INSERT INTO project_metadata (project_id,  abstract, data_owner, contact_email, orcid_id, 
                        other_contributors, funding_information, data_license, latitude, longitude, time_zone, unit_of_measurement,
                        sensor_make_and_type, sensor_accuracy, sampling_method, related_publication, additional_notes, version)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                '''

                data_values = (
                    project_id, abstract, data_owner, contact_email, orcid_id,
                    other_contributors, funding_information, data_license,
                    latitude, longitude, time_zone, unit_of_measurement,
                    sensor_make_and_type, sensor_accuracy, sampling_method,
                    related_publication, additional_notes, new_version
                )

                cursor.execute(insert_query, data_values)
                connection.commit()
                
                # Close the cursor and connection
                close_mysql_connection(connection, cursor)

                return jsonify({'message': 'Metadata uploaded successfully as a new version'})
            else:
                new_version = generate_version(location, longitude, latitude, selected_measurement, "version1")

                print(f'Project ID: {project_id}, New Version: {new_version}')

                insert_query = '''
                    INSERT INTO project_metadata (project_id,  abstract, data_owner, contact_email, orcid_id, 
                        other_contributors, funding_information, data_license, latitude, longitude, time_zone, unit_of_measurement,
                        sensor_make_and_type, sensor_accuracy, sampling_method, related_publication, additional_notes, version)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                '''

                data_values = (
                    project_id, abstract, data_owner, contact_email, orcid_id,
                    other_contributors, funding_information, data_license,
                    latitude, longitude, time_zone, unit_of_measurement,
                    sensor_make_and_type, sensor_accuracy, sampling_method,
                    related_publication, additional_notes, new_version
                )

                cursor.execute(insert_query, data_values)
                connection.commit()
                
                # Close the cursor and connection
                close_mysql_connection(connection, cursor)

                return jsonify({'message': 'Metadata uploaded successfully as a new version'})
        else:
            create_project_query = 'INSERT INTO projects (project_name) VALUES (%s)'
            cursor.execute(create_project_query, (project_name,))
            connection.commit()
            
            # Close the cursor and connection
            close_mysql_connection(connection, cursor)

            cursor.execute(check_project_query, (project_name,))
            project_result = cursor.fetchone()

            if project_result:
                project_id = project_result[0]

                new_version = generate_version(location, longitude, latitude, selected_measurement, "version1")

                print(f'Project ID: {project_id}, New Version: {new_version}')

                insert_query = '''
                    INSERT INTO project_metadata (project_id,  abstract, data_owner, contact_email, orcid_id, 
                        other_contributors, funding_information, data_license, latitude, longitude, time_zone, unit_of_measurement,
                        sensor_make_and_type, sensor_accuracy, sampling_method, related_publication, additional_notes, version)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                '''

                data_values = (
                    project_id, abstract, data_owner, contact_email, orcid_id,
                    other_contributors, funding_information, data_license,
                    latitude, longitude, time_zone, unit_of_measurement,
                    sensor_make_and_type, sensor_accuracy, sampling_method,
                    related_publication, additional_notes, new_version
                )

                cursor.execute(insert_query, data_values)
                connection.commit()
                
                # Close the cursor and connection
                close_mysql_connection(connection, cursor)

                return jsonify({'message': 'Metadata uploaded successfully as a new version'})
            else:
                # Handle an unexpected error, project should exist at this point
                return jsonify({'message': 'Unexpected error'})
    except Exception as e:
        # Handle the exception and roll back the transaction
        print(f"Error in submit_metadata: {e}")
        connection.rollback()
        
        # Close the cursor and connection
        close_mysql_connection(connection, cursor)

        return jsonify({'message': 'Error occurred, transaction rolled back'})
  
    

    
def generate_version(location, longitude, latitude, measurement_name, version):
    # Extract numeric part after '-version'
    numeric_part = version.split('-version')[-1]

    # Check if the numeric part is not empty and is a digit
    if numeric_part.isdigit():
        new_version = int(numeric_part) + 1
        return f'{location}-{longitude}-{latitude}-{measurement_name}-version{new_version}'
    else:
        # Handle the case where the numeric part is empty or not a digit
        print(f'Invalid version format: {version}')
        # If there's no version for the project, set version to 1
        return f'{location}-{longitude}-{latitude}-{measurement_name}-version1'

 

########################################################################################################################################################################################################################################
########################################################################################################################################################################################################################################
########################################################################################################################################################################################################################################











client = InfluxDBClient(url=influxdb_url, token=influxdb_token, org=influxdb_org)
query_api = client.query_api()




@app.route('/search', methods=['POST'])
def search():
    try:
        data = request.get_json()

        selected_measurement = data.get('selectedMeasurement')
        selected_fields = data.get('selectedFields')
        start_time_str = data.get('startDate')
        stop_time_str = data.get('endDate')
        data_creator = data.get('dataCreator')
        location = data.get('data_Location')  # Added location parameter
        project_name = data.get('ProjectName')
       
        print(f"Received Data Creator: {data_creator}")
        print(f"Received location: {location}")
        print(f"Received location: {project_name}")

        # Convert start_time and stop_time to RFC3339 format
        try:
            start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').isoformat() + 'Z'
            stop_time = datetime.strptime(stop_time_str, '%Y-%m-%d %H:%M:%S').isoformat() + 'Z'
        except ValueError:
            return jsonify({'error': 'Invalid date format'}), 400

        print(f"Start Time: {start_time}, Stop Time: {stop_time}")

        query_api = client.query_api()

        # Construct the InfluxDB query
        query = f'''
        from(bucket: "{influxdb_bucket}")
             |> range(start: {start_time}, stop: {stop_time})
            |> filter(fn: (r) => r["_measurement"] == "{selected_measurement}")
        '''

        # Check if selected_fields is not empty before adding field filters
        if selected_fields:
            query += '|> filter(fn: (r) => '
            query += ' or '.join([f'r["_field"] == "{field}"' for field in selected_fields])
            query += ')'

        if data_creator:
            query += f'|> filter(fn: (r) => r["data_creator"] == "{data_creator}")'
        if location:
            query += f'|> filter(fn: (r) => r["location"] == "{location}")'
        if project_name:
            query += f'|> filter(fn: (r) => r["project_name"] == "{project_name}")'     

        print(f"InfluxDB Query: {query}")

        try:
            result = query_api.query(query)
        except InfluxDBServerError as e:
            print(f'InfluxDB Server Error: {str(e)}')
            return jsonify({'error': f'InfluxDB Server Error: {str(e)}'}), 500
        except InfluxDBClientError as e:
            print(f'InfluxDB Client Error: {str(e)}')
            return jsonify({'error': f'InfluxDB Client Error: {str(e)}'}), 500

        # Check if the result is empty
        if not result:
            print('No data found for the given criteria')
            return jsonify({'error': 'No data found for the given criteria'}), 404

        # Convert the result to a pandas DataFrame
        data_list = []
        for table in result:
            for record in table.records:
                data_list.append({
                    'Time': record.get_time().strftime('%Y-%m-%d %H:%M:%S'),
                    'Measurement': record.get_measurement(),
                    'Field': record.get_field(),
                    'Value': record.get_value(),
                })

        try:
            df = DataFrame(data_list)
            df = df.drop_duplicates()  # Drop duplicate rows
            df_pivot = df.pivot(index='Time', columns='Field', values='Value').reset_index()
        except Exception as e:
            print(f'Error converting data to DataFrame: {str(e)}')
            return jsonify({'error': f'Error converting data to DataFrame: {str(e)}'}), 500

        # Convert the pivoted DataFrame to JSON
        json_data = df_pivot.to_json(orient='records')

        return json_data

    except Exception as e:
        print(f'An unexpected error occurred: {str(e)}')
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500





@app.route('/delete/<username>', methods=['POST'])
def delete_data(username):
    try:
        data = request.get_json()
        # Extract necessary parameters
        selectedMeasurement = data.get('selectedMeasurement')
        start_time_str = data.get('startDate')
        stop_time_str = data.get('endDate')
        location = data.get('data_Location')
        data_creator = data.get('dataCreator')
        print(username)
        print(data_creator)
        # Check if the provided username matches the data_creator
        # Check if the provided username matches the data_creator
        if username != data_creator:
            return jsonify({'error': 'Unauthorized. Username and data creator do not match.'}), 401       
        
        print(f"Matched: {data_creator}")
        # Convert start_time and stop_time to RFC3339 format
        start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S').isoformat() + 'Z'
        stop_time = datetime.strptime(stop_time_str, '%Y-%m-%d %H:%M:%S').isoformat() + 'Z'
        print(f"Received Data for Deletion - Measurement: {selectedMeasurement}, Data Creator: {data_creator}")
        print(f"Start Time: {start_time}, Stop Time: {stop_time}")
        # Construct the InfluxDB delete query
        delete_query = f'_measurement="{selectedMeasurement}" AND data_creator="{data_creator}"'
        if location:
            delete_query += f' AND location="{location}"'      

        # Prepare data for the InfluxDB delete request
        delete_data = {
            "start": start_time,
            "stop": stop_time,
            "predicate": delete_query
        }
        # InfluxDB API endpoint
        influxdb_url = f'{influxdb_url}/api/v2/delete?org={influxdb_org}&bucket={influxdb_bucket}'
        # InfluxDB API Token
        influxdb_token = influxdb_token
        # Headers for the delete request
        headers = {
            'Authorization': f'Token {influxdb_token}',
            'Content-Type': 'application/json'
        }

        # Make the InfluxDB delete request
        response = requests.post(influxdb_url, json=delete_data, headers=headers)
        # Check the response status
        if response.status_code == 204:
            return jsonify({'message': 'Data deleted successfully'})
        else:
            return jsonify({'error': f'Failed to delete data check the querry. InfluxDB API response: {response.text}'}), 500
    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500


@app.route('/metadata', methods=['GET'])
def get_metadata():
    try:
        # Get project_name from query parameters
        project_name = request.args.get('project_name')

        if not project_name:
            return jsonify({'error': 'Project name is required'}), 400

        # Using a connection from the pool
        with mysql_pool.get_connection() as connection:
            with connection.cursor() as cursor:
                try:
                    cursor.execute(f"SELECT project_id FROM projects WHERE project_name = '{project_name}'")
                    result = cursor.fetchone()
                except Exception as e:
                    return jsonify({'error': f'Error querying project from MySQL: {str(e)}'}), 500

                if not result:
                    return jsonify({'error': 'Project not found'}), 200  # Returning 200 for a successful response with an error message

                user_project_id = result[0]

                # Query MySQL to get project metadata based on project ID
                try:
                    cursor.execute(f"SELECT * FROM project_metadata WHERE project_id = {user_project_id}")
                    metadata_result = cursor.fetchall()
                except Exception as e:
                    return jsonify({'error': f'Error querying metadata from MySQL: {str(e)}'}), 500
                

                # Convert the metadata_result to a list of dictionaries
                metadata_list = []
                for row in metadata_result:
                    metadata_dict = {
                        'project_id': row[1],
                        'abstract': row[2],
                        'data_owner': row[3],
                        'contact_email': row[4],
                        'orcid_id': row[5],
                        'other_contributors': row[6],
                        'funding_information': row[7],
                        'data_license': row[8],
                        'latitude': row[9],
                        'longitude': row[10],
                        'time_zone': row[11],
                        'unit_of_measurement': row[12],
                        'sensor_make_and_type': row[13],
                        'sensor_accuracy': row[14],
                        'sampling_method': row[15],
                        'related_publication': row[16],
                        'additional_notes': row[17],
                        'version': row[18],
                        'label': row[19]
                        # Add more fields as needed
                    }
                    metadata_list.append(metadata_dict)

                return jsonify(metadata_list)

    except Exception as e:
        return jsonify({'error': f'An unexpected error occurred: {str(e)}'}), 500
    finally:
        close_mysql_connection(connection, cursor)




if __name__ == '__main__':
    app.run(debug=True)
