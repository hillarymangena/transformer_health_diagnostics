// Chart instances
let charts = {};

// Initialize charts
function initializeCharts() {
    const chartConfigs = [
        { id: 'currentChart', label: 'Sec. Current (A)', params: ['current'], max: { TX1: 150, TX2: 3000, TX3: 150 }},
        { id: 'voltageChart', label: 'Sec. Vol. (V)', params: ['voltage'], max: { TX1: 430, TX2: 430, TX3: 430 }},
        { id: 'temperatureChart', label: 'Temp. (°C)', params: ['temperature'], max: { TX1: 70, TX2: 70, TX3: 70 }},
        { id: 'vibrationsChart', label: 'Vibr. (m⋅s−2)', params: ['vibrations'], max: { TX1: 2.0, TX2: 2.0, TX3: 2.0 }},
        { id: 'dgaChart', label: 'DGA (ppm)', params: ['dga'], transformers: ['TX2'], max: { TX2: 200 }},
        { id: 'moistureChart', label: 'Moisture (ppm)', params: ['moisture'], max: { TX1: 30, TX2: 30, TX3: 30 }}
    ];

    chartConfigs.forEach(config => {
        const ctx = document.getElementById(config.id).getContext('2d');
        const datasets = (config.transformers || ['TX1', 'TX2', 'TX3']).map(tx => ({
            label: tx,
            data: [],
            borderColor: tx === 'TX1' ? '#90ee90' : tx === 'TX2' ? '#dc143c' : '#4169e1',
            backgroundColor: 'transparent',
            fill: false,
            pointStyle: 'circle',
            pointRadius: 5,
            pointBackgroundColor: 'transparent',
            pointBorderColor: tx === 'TX1' ? '#90ee90' : tx === 'TX2' ? '#dc143c' : '#4169e1',
            tension: 0,
            borderWidth: 1
        }));

        charts[config.id] = new Chart(ctx, {
            type: 'line',
            data: { labels: [], datasets },
            options: {
                scales: {
                    x: { title: { display: true, text: 'Time' } },
                    y: { title: { display: true, text: config.label } }
                },
                plugins: {
                    legend: { display: false },
                    annotation: {
                        annotations: (config.transformers || ['TX1', 'TX2', 'TX3']).map(tx => ({
                            type: 'line',
                            yMin: config.max[tx],
                            yMax: config.max[tx],
                            borderColor: '#666',
                            borderWidth: 1,
                            borderDash: [5, 5]
                        }))
                    }
                }
            }
        });
    });
}

// Update date and time every second
function updateDateTime() {
    const now = new Date();
    const dateTimeString = now.toLocaleString('en-GB', {
        day: '2-digit',
        month: '2-digit',
        year: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    document.getElementById('datetime').textContent = dateTimeString;
}

// Fetch and display alerts and graphs
function fetchAlerts() {
    fetch('/api/alerts')
        .then(response => response.json())
        .then(data => {
            // Debug: Log raw data
            console.log('API Response:', data);

            // Update alerts
            const container = document.getElementById('alerts-container');
            container.innerHTML = '';
            data.forEach(transformer => {
                const alertBox = document.createElement('div');
                alertBox.className = 'alert-box';
                
                const title = document.createElement('h3');
                title.textContent = transformer.transformer;
                alertBox.appendChild(title);
                
                const specs = document.createElement('p');
                specs.textContent = transformer.specs;
                alertBox.appendChild(specs);
                
                transformer.alerts.forEach(alert => {
                    const alertDiv = document.createElement('div');
                    alertDiv.className = `alert ${alert.color}`;
                    alertDiv.textContent = `${alert.timestamp} STATUS - ${alert.status}`;
                    alertBox.appendChild(alertDiv);
                });
                
                container.appendChild(alertBox);
            });

            // Update graphs
            const labels = data.find(t => t.transformer.includes('TX1'))?.graph_data.current.map(d => d.timestamp.split(' ')[1]) || [];
            console.log('Graph Labels:', labels);

            Object.keys(charts).forEach(chartId => {
                const param = chartId.replace('Chart', '').toLowerCase();
                charts[chartId].data.labels = labels;
                charts[chartId].data.datasets.forEach(dataset => {
                    const tx = dataset.label;
                    const transformer = data.find(t => t.transformer.includes(tx));
                    if (transformer && transformer.graph_data[param] && transformer.graph_data[param].length > 0) {
                        dataset.data = transformer.graph_data[param].map(d => d.value);
                        console.log(`Data for ${tx} - ${param}:`, dataset.data);
                    } else {
                        console.log(`No data for ${tx} - ${param}, using fallback`);
                        dataset.data = Array(labels.length).fill(0);
                    }
                });
                charts[chartId].update();
            });
        })
        .catch(error => console.error('Error fetching data:', error));
}

// Hamburger menu toggle
document.querySelector('.hamburger').addEventListener('click', () => {
    document.getElementById('menu-items').classList.toggle('active');
});

// Initial calls
initializeCharts();
updateDateTime();
fetchAlerts();

// Update date/time every second
setInterval(updateDateTime, 1000);

// Fetch alerts and graphs every 30 seconds
setInterval(fetchAlerts, 30000);