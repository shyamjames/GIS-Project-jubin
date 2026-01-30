document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Map
    // Focusing on Rajagiri Valley/Kochi area
    const map = L.map('map').setView([10.028, 76.308], 15);

    // Dark Mode Map Tiles
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: 'abcd',
        maxZoom: 20
    }).addTo(map);

    // Layer Group for Markers
    const markersLayer = L.layerGroup().addTo(map);

    // Heatmap Layer (Congestion Intensity)
    // Heatmap Layer (Congestion Intensity)
    const beatLayer = L.heatLayer([], {
        radius: 25,  // Reduced from 45 to tightly hug the road
        blur: 30,    // Reduced from 60 for better definition
        maxZoom: 17,
        max: 1.0,    // Hard cap for intensity
        // Standard Traffic Gradient: Transparent -> Green -> Yellow -> Orange -> Red
        gradient: {
            0.2: '#00ff00', // Green (Flowing) - Start visible range here
            0.5: '#ffff00', // Yellow (Moderate)
            0.8: '#ff8000', // Orange (Heavy)
            1.0: '#ff0000'  // Red (Severe/Gridlock)
        }
    }).addTo(map);

    // 2. Initialize Chart
    const ctx = document.getElementById('vehicleChart').getContext('2d');
    const vehicleChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Car', 'Bike', 'Bus', 'Truck'],
            datasets: [{
                label: 'Vehicle Dist.',
                data: [0, 0, 0, 0],
                backgroundColor: [
                    '#00d4ff', // Car - Blue
                    '#ffcc00', // Bike - Yellow
                    '#ff4444', // Bus - Red
                    '#44ff44'  // Truck - Green
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { color: '#fff' }
                }
            }
        }
    });

    // 3. Fetch Data & Update UI
    function fetchData() {
        fetch('/api/data')
            .then(response => response.json())
            .then(data => {
                updateDashboard(data);
            })
            .catch(err => console.error('Error fetching data:', err));
    }

    function updateDashboard(data) {
        // Update Total Count
        document.getElementById('total-count').innerText = data.total_vehicles;

        // Update Chart
        const dist = data.distribution;
        vehicleChart.data.datasets[0].data = [
            dist.car, dist.bike, dist.bus, dist.truck
        ];
        vehicleChart.update();

        // Update Heatmap Data (Point-Based Congestion Intensity)
        const heatPoints = data.locations.map(loc => [loc.lat, loc.lng, loc.weighted_intensity]);
        beatLayer.setLatLngs(heatPoints);

        // Update Map Markers
        markersLayer.clearLayers();
        const alertsList = document.getElementById('alerts-list');
        alertsList.innerHTML = ''; // Clear old alerts

        data.locations.forEach(loc => {
            const isLive = loc.source_type === 'live_cctv';

            // Determine Color based on Intensity Label
            let color = '#00ff00'; // Default Green (Low/Flowing)
            if (loc.intensity === 'low') color = '#00ff00';     // Green
            if (loc.intensity === 'moderate') color = '#ffff00'; // Yellow
            if (loc.intensity === 'high') color = '#ff0000';     // Red (no longer orange/red splitter)
            if (loc.intensity === 'congestion') color = '#ff0000'; // Red

            // Differentiated Marker Style
            const markerOptions = {
                radius: isLive ? 12 : 6, // Larger for Live
                fillColor: color,
                color: isLive ? '#fff' : 'transparent', // White border for Live
                weight: isLive ? 3 : 0,
                opacity: 1,
                fillOpacity: isLive ? 0.9 : 0.5 // Translucent for simulated
            };

            const marker = L.circleMarker([loc.lat, loc.lng], markerOptions);

            // Add Pulsing Effect for Live Nodes (via CSS class if possible, or simple style)
            if (isLive) {
                // We can use a custom icon for pulsing, but for now circleMarker is simple. 
                // Let's add a className if Leaflet supports it natively on CircleMarker (it acts as SVG).
                // Alternatively, bind a specific popup class.
                marker.setStyle({ className: 'live-marker-pulse' });
            }

            // Popup Info
            const saturation = Math.round((loc.total / (loc.lanes ? loc.lanes * 4 : 50)) * 100);

            const popupContent = `
                <div style="color: #000; text-align:center;">
                    <h3 style="margin: 0 0 5px;">${loc.name}</h3>
                    <div style="font-size:0.8rem; margin-bottom: 5px;">
                        <span style="background:${color}; color:${color === '#ffff00' ? '#000' : '#fff'}; padding:2px 8px; border-radius:10px; opacity: 1;">
                            ${loc.intensity.toUpperCase()}
                        </span>
                    </div>
                    <p style="font-size:0.7rem; margin-top:5px; color:#555;">
                        Count: <strong>${loc.total}</strong> | Lanes: <strong>${loc.lanes || 2}</strong><br>
                        Saturation: ${saturation > 100 ? 100 : saturation}%
                    </p>
                    <p style="font-size:0.7rem; color:#777;">
                        ${isLive ? '🔴 LIVE FEED' : 'Modeled Data'}
                    </p>
                </div>
            `;

            marker.bindPopup(popupContent);

            // Interaction: Click to View Feed (ONLY for Live)
            marker.on('click', () => {
                if (isLive) {
                    const img = document.querySelector('.live-feed-card img');
                    const title = document.querySelector('.live-feed-card h3');

                    if (img && title) {
                        img.src = '/video_feed/' + loc.id + '?t=' + new Date().getTime();
                        title.innerText = 'Live Feed: ' + loc.name;
                        // Ensure live dot is visible
                        document.querySelector('.rec-dot').style.display = 'block';
                    }
                } else {
                    // For simulated, maybe show a static placeholder or just do nothing/show alert
                    const img = document.querySelector('.live-feed-card img');
                    const title = document.querySelector('.live-feed-card h3');

                    if (img && title) {
                        // Optional: Set to a placeholder image or keep previous
                        // title.innerText = 'Analysis: ' + loc.name;
                        // img.src = ''; // Clear or set placeholder
                        console.log("Clicked simulated node");
                    }
                }
            });

            markersLayer.addLayer(marker);

            // Add Side Panel Alert if High Traffic AND Live/Significant
            if (loc.intensity === 'high' && (isLive || loc.total > 45)) {
                const li = document.createElement('li');
                li.innerHTML = `<strong style="color: #ff4444;">CONGESTION:</strong> ${loc.name}`;
                alertsList.appendChild(li);
            }
        });
    }

    // Poll every 2 seconds
    setInterval(fetchData, 2000);
    fetchData(); // Initial Call
});
