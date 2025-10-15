from flask import Flask, render_template, request, jsonify, send_file
from langchain_ollama import OllamaLLM, OllamaEmbeddings
from langchain_chroma import Chroma
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document
from langchain.chains import RetrievalQA
import sqlite3
import json
import os
from datetime import datetime, timedelta
import random
from threading import Thread
import time

app = Flask(__name__)

# Initialize LLM and Embeddings with error handling
try:
    llm = OllamaLLM(model="llama3.2:latest", base_url="http://localhost:11434")
except Exception as e:
    print(f"Error initializing Ollama LLM: {e}")
    llm = None

try:
    embeddings = OllamaEmbeddings(model="mxbai-embed-large:latest", base_url="http://localhost:11434")
except Exception as e:
    print(f"Error initializing Ollama Embeddings: {e}")
    embeddings = None

# Fallback if LLM/Embeddings fail
if llm is None or embeddings is None:
    raise Exception("LLM or Embeddings initialization failed. Ensure Ollama is running locally on port 11434.")

# Initialize Chroma vector store
try:
    vector_store = Chroma(embedding_function=embeddings, persist_directory="./chroma_db")
except Exception as e:
    print(f"Error initializing Chroma vector store: {e}")
    vector_store = None

# SQLite database setup
def init_db():
    try:
        conn = sqlite3.connect('transformer_data.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS sensor_data 
                     (id INTEGER PRIMARY KEY, transformer_id TEXT, timestamp TEXT, current REAL, voltage REAL, 
                      temperature REAL, vibrations REAL, dga REAL, moisture REAL)''')
        c.execute('''CREATE TABLE IF NOT EXISTS uploaded_files 
                     (id INTEGER PRIMARY KEY, filename TEXT, content TEXT, timestamp TEXT)''')
        conn.commit()
    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
    finally:
        conn.close()

init_db()

# Simulated data storage and status determination (from your original code)
data_store = {
    "TX1": {"current": [], "voltage": [], "temperature": [], "vibrations": [], "moisture": []},
    "TX2": {"current": [], "voltage": [], "temperature": [], "vibrations": [], "dga": [], "moisture": []},
    "TX3": {"current": [], "voltage": [], "temperature": [], "vibrations": [], "moisture": []}
}

normal_ranges = {
    "current": {"TX1": (120, 150), "TX2": (2500, 3000), "TX3": (120, 150)},
    "voltage": {"TX1": (400, 430), "TX2": (400, 430), "TX3": (400, 430)},
    "temperature": {"TX1": (30, 70), "TX2": (30, 70), "TX3": (30, 70)},
    "vibrations": {"TX1": (0.5, 2.0), "TX2": (0.5, 2.0), "TX3": (0.5, 2.0)},
    "dga": {"TX2": (50, 200)},
    "moisture": {"TX1": (10, 30), "TX2": (10, 30), "TX3": (10, 30)}
}

def simulate_data():
    timestamp = datetime.now().strftime("%d-%m-%y %H:%M:%S")
    data = {"timestamp": timestamp, "transformers": {}}
    for tx in ["TX1", "TX2", "TX3"]:
        data["transformers"][tx] = {}
        params = ["current", "voltage", "temperature", "vibrations", "moisture"]
        if tx == "TX2":
            params.append("dga")
        if tx == "TX2":
            normal_param = random.choice(params)
        else:
            normal_param = None
        for param in params:
            min_val, max_val = normal_ranges[param][tx]
            if tx == "TX2" and param == normal_param:
                val = random.uniform(min_val, max_val)
            else:
                val = random.uniform(min_val * 0.8, max_val * 1.2)
            val = round(val, 2)
            data["transformers"][tx][param] = val
            data_store[tx][param].append({"value": val, "timestamp": timestamp})
            if len(data_store[tx][param]) > 5:
                data_store[tx][param].pop(0)
    return data

def determine_status(tx, data):
    alerts = []
    params = ["current", "voltage", "temperature", "vibrations", "moisture"]
    if tx == "TX2":
        params.append("dga")
    base_timestamp = datetime.strptime(data["timestamp"], "%d-%m-%y %H:%M:%S")
    deviations = []
    for param in params:
        val = data["transformers"][tx][param]
        min_val, max_val = normal_ranges[param][tx]
        if val >= min_val and val <= max_val:
            deviations.append({"param": "OK", "color": "green"})
        elif val < min_val * 0.9 or val > max_val * 1.1:
            deviation = abs((val - (min_val + max_val) / 2) / ((min_val + max_val) / 2)) * 100
            color = "red" if deviation >= 10 else "yellow"
            deviations.append({"param": param.upper() + " ALERT", "color": color})
        elif val < min_val or val > max_val:
            deviation = abs((val - (min_val + max_val) / 2) / ((min_val + max_val) / 2)) * 100
            color = "red" if deviation >= 10 else "yellow"
            deviations.append({"param": param.upper() + " ALERT", "color": color})
    if tx == "TX1":
        alerts = [{"param": "OK", "color": "green"}]
        possible_alerts = [a for a in deviations if a["param"] != "MULTIPLE" and a["param"] != "OK"]
        alerts.extend(random.sample(possible_alerts, min(2, len(possible_alerts))))
        while len(alerts) < 3:
            alerts.append({"param": random.choice(["TEMPERATURE ALERT", "VIBRATIONS ALERT"]), "color": "yellow"})
    elif tx == "TX2":
        ok_alerts = [a for a in deviations if a["param"] == "OK"]
        other_alerts = [a for a in deviations if a["param"] != "OK"]
        alerts = []
        alerts.append({"param": "MULTIPLE", "color": "orange"})
        if ok_alerts:
            alerts.append(random.choice(ok_alerts))
        else:
            alerts.append({"param": "OK", "color": "green"})
        if other_alerts:
            alerts.append(random.choice(other_alerts))
        else:
            alerts.append({"param": random.choice(["TEMPERATURE ALERT", "VIBRATIONS ALERT"]), "color": "yellow"})
    elif tx == "TX3":
        alerts = [{"param": "OK", "color": "green"} for _ in range(3)]
    for i, alert in enumerate(alerts):
        offset = i * 3
        alert_timestamp = base_timestamp - timedelta(minutes=1) + timedelta(minutes=offset)
        alerts[i] = {
            "timestamp": alert_timestamp.strftime("%d-%m-%y %H:%M:%S"),
            "status": alert["param"],
            "color": alert["color"]
        }
    return alerts

# Store sensor data in SQLite (triggered by periodic simulation)
def store_sensor_data(transformer_id, current, voltage, temperature, vibrations, dga, moisture):
    try:
        conn = sqlite3.connect('transformer_data.db')
        c = conn.cursor()
        c.execute('''INSERT INTO sensor_data (transformer_id, timestamp, current, voltage, temperature, 
                     vibrations, dga, moisture) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (transformer_id, datetime.now().isoformat(), current, voltage, temperature, vibrations, dga, moisture))
        conn.commit()
    except sqlite3.Error as e:
        print(f"SQLite insertion error: {e}")
    finally:
        conn.close()

# Periodic data simulation (stores data in SQLite)
def simulate_periodically():
    while True:
        data = simulate_data()
        for tx, values in data["transformers"].items():
            store_sensor_data(tx, values["current"], values["voltage"], values["temperature"],
                             values["vibrations"], values.get("dga", 0), values["moisture"])
        time.sleep(30)  # Simulate every 30 seconds

Thread(target=simulate_periodically, daemon=True).start()

# Pre-process and store uploaded file
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    try:
        content = file.read().decode('utf-8')
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        docs = [Document(page_content=x) for x in text_splitter.split_text(content)]
        vector_store.add_documents(docs)
        conn = sqlite3.connect('transformer_data.db')
        c = conn.cursor()
        c.execute('INSERT INTO uploaded_files (filename, content, timestamp) VALUES (?, ?, ?)',
                  (file.filename, content, datetime.now().isoformat()))
        conn.commit()
    except Exception as e:
        return jsonify({"error": f"Upload processing failed: {e}"}), 500
    finally:
        conn.close()
    return jsonify({"message": "File uploaded and processed for RAG"}), 200

# Chat functionality
@app.route('/chat', methods=['POST'])
def chat():
    if llm is None or vector_store is None:
        return jsonify({"error": "LLM or vector store not initialized"}), 500
    user_message = request.json.get('message')
    try:
        retriever = vector_store.as_retriever()
        qa_chain = RetrievalQA.from_chain_type(llm=llm, chain_type="stuff", retriever=retriever)
        response = qa_chain.invoke({"query": user_message})  # Updated to invoke
    except Exception as e:
        return jsonify({"error": f"Chat processing failed: {e}"}), 500
    return jsonify({"response": response.get("result", "No response")})

# Maintenance Plan Generation
@app.route('/generate_maintenance_plan', methods=['GET'])
def generate_maintenance_plan():
    if llm is None:
        return jsonify({"error": "LLM not initialized"}), 500
    try:
        conn = sqlite3.connect('transformer_data.db')
        c = conn.cursor()
        twenty_four_hours_ago = (datetime.now() - timedelta(hours=24)).isoformat()
        c.execute('SELECT * FROM sensor_data WHERE timestamp >= ? ORDER BY timestamp DESC',
                  (twenty_four_hours_ago,))
        sensor_data = c.fetchall()
        if not sensor_data:
            c.execute('SELECT * FROM sensor_data ORDER BY timestamp DESC')
            sensor_data = c.fetchall()
    except sqlite3.Error as e:
        return jsonify({"error": f"Database query failed: {e}"}), 500
    finally:
        conn.close()

    # Prepare context for LLM with data over the last 24 hours or all
    context = "Sensor Data (Transformer ID, Timestamp, Current, Voltage, Temperature, Vibrations, DGA, Moisture):\n"
    for row in sensor_data:
        context += f"{row[1]}, {row[2]}, {row[3]}, {row[4]}, {row[5]}, {row[6]}, {row[7]}, {row[8]}\n"
    context += "\nTask: Generate a maintenance plan for each transformer (TX1, TX2, TX3) based on the sensor data from the last 24 hours or all available data. For each transformer, decide if it requires 'Fixing Issues' or 'Predictive Maintenance'. Include issues/faults, possible causes, how to fix, and required tools. Use explainable AI with clear logical steps. Normal ranges: Current (TX1: 120-150A, TX2: 2500-3000A, TX3: 120-150A), Voltage (400-430V), Temperature (30-70°C), Vibrations (0.5-2.0 ms^-2), DGA (50-200 ppm for TX2), Moisture (10-30 ppm)."

    # LLM thinking indicator and explainable AI
    thought_process = ["Analyzing sensor data over the last 24 hours or all available data..."]
    try:
        response = llm.invoke(context)
        thought_process.append("LLM processing: " + response)
    except Exception as e:
        return jsonify({"error": f"LLM invocation failed: {e}"}), 500

    # Parse LLM response (assuming structured text output)
    maintenance_plans = {}
    current_transformer = None
    for line in response.split('\n'):
        if line.startswith("Transformer: "):
            current_transformer = line.replace("Transformer: ", "").strip()
            maintenance_plans[current_transformer] = {}
        elif current_transformer and any(key in line for key in ["Type:", "Issues:", "Causes:", "Fixes:", "Tools:"]):
            key, value = line.split(":", 1)
            maintenance_plans[current_transformer][key.strip().lower()] = value.strip()

    return render_template('maintenance_plan.html', plans=maintenance_plans, thought_process=thought_process)

# Download Maintenance Plan
@app.route('/download_plan')
def download_plan():
    if llm is None:
        return jsonify({"error": "LLM not initialized"}), 500
    try:
        conn = sqlite3.connect('transformer_data.db')
        c = conn.cursor()
        twenty_four_hours_ago = (datetime.now() - timedelta(hours=24)).isoformat()
        c.execute('SELECT * FROM sensor_data WHERE timestamp >= ? ORDER BY timestamp DESC',
                  (twenty_four_hours_ago,))
        sensor_data = c.fetchall()
        if not sensor_data:
            c.execute('SELECT * FROM sensor_data ORDER BY timestamp DESC')
            sensor_data = c.fetchall()
    except sqlite3.Error as e:
        return jsonify({"error": f"Database query failed: {e}"}), 500
    finally:
        conn.close()

    context = "Sensor Data (Transformer ID, Timestamp, Current, Voltage, Temperature, Vibrations, DGA, Moisture):\n"
    for row in sensor_data:
        context += f"{row[1]}, {row[2]}, {row[3]}, {row[4]}, {row[5]}, {row[6]}, {row[7]}, {row[8]}\n"
    context += "\nTask: Generate a maintenance plan in human-readable format for each transformer (TX1, TX2, TX3) based on the sensor data from the last 24 hours or all available data. Include Type, Issues/Faults, Possible Causes, How to Fix, and Required Tools. Normal ranges: Current (TX1: 120-150A, TX2: 2500-3000A, TX3: 120-150A), Voltage (400-430V), Temperature (30-70°C), Vibrations (0.5-2.0 ms^-2), DGA (50-200 ppm for TX2), Moisture (10-30 ppm)."

    try:
        response = llm.invoke(context)
    except Exception as e:
        return jsonify({"error": f"LLM invocation failed: {e}"}), 500

    plan_text = "Maintenance Plan (Generated at " + datetime.now().strftime("%I:%M %p SAST, %B %d, %Y") + ")\n\n"
    current_transformer = None
    for line in response.split('\n'):
        if line.startswith("Transformer: "):
            if current_transformer:
                plan_text += "\n"
            current_transformer = line.replace("Transformer: ", "").strip()
            plan_text += f"{line}\n"
        elif current_transformer and any(key in line for key in ["Type:", "Issues:", "Causes:", "Fixes:", "Tools:"]):
            plan_text += f"{line}\n"

    try:
        with open('maintenance_plan.txt', 'w') as f:
            f.write(plan_text)
    except Exception as e:
        return jsonify({"error": f"File write failed: {e}"}), 500
    return send_file('maintenance_plan.txt', as_attachment=True)

# Prompt Engineering Section
@app.route('/prompt_engineering', methods=['GET', 'POST'])
def prompt_engineering():
    if llm is None:
        return jsonify({"error": "LLM not initialized"}), 500
    if request.method == 'POST':
        custom_prompt = request.form.get('custom_prompt')
        try:
            with open('prompts.txt', 'a') as f:
                f.write(f"{custom_prompt}\n")
        except Exception as e:
            return jsonify({"error": f"Prompt save failed: {e}"}), 500
        return jsonify({"message": "Prompt saved"})
    return render_template('prompt_engineering.html')

# Main route with alerts
@app.route('/')
def index():
    data = simulate_data()
    alerts_data = [
        {
            "transformer": f"{tx} - {'Midrand' if tx == 'TX1' else 'Birch Acres' if tx == 'TX2' else 'Kempton West'}",
            "specs": (
                "100 kVA, 33’000/415 V, 139 A (LV), ONAN, 3Φ, DYN-11, pole mounted" if tx == "TX1" else
                "2 MVA, 11’000/415 V, 2778 A (LV), ONAF, 3Φ, DYN-11, ground mounted" if tx == 'TX2' else
                "100 kVA, 1100/415 V, 139 A (LV), ONAN, 3Φ, DYN-11, pole mounted"
            ),
            "alerts": determine_status(tx, data),
            "graph_data": data_store[tx]
        } for tx in ["TX1", "TX2", "TX3"]
    ]
    return render_template('index.html', alerts_data=alerts_data)

# API endpoint for alerts (REST)
@app.route('/api/alerts')
def get_alerts():
    data = simulate_data()
    alerts_data = [
        {
            "transformer": f"{tx} - {'Midrand' if tx == 'TX1' else 'Birch Acres' if tx == 'TX2' else 'Kempton West'}",
            "specs": (
                "100 kVA, 33’000/415 V, 139 A (LV), ONAN, 3Φ, DYN-11, pole mounted" if tx == "TX1" else
                "2 MVA, 11’000/415 V, 2778 A (LV), ONAF, 3Φ, DYN-11, ground mounted" if tx == 'TX2' else
                "100 kVA, 1100/415 V, 139 A (LV), ONAN, 3Φ, DYN-11, pole mounted"
            ),
            "alerts": determine_status(tx, data),
            "graph_data": data_store[tx]
        } for tx in ["TX1", "TX2", "TX3"]
    ]
    return jsonify(alerts_data)

if __name__ == '__main__':
    app.run(debug=True)