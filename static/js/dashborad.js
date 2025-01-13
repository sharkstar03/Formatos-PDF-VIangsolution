// Configuración de gráficos
const chartConfig = {
    monthlyChart: {
        options: {
            chart: {
                type: 'bar',
                height: 350
            },
            colors: ['#4F46E5', '#93C5FD'],
            plotOptions: {
                bar: {
                    horizontal: false,
                    columnWidth: '55%',
                    endingShape: 'rounded'
                },
            }
        }
    },
    regionalChart: {
        options: {
            chart: {
                type: 'pie',
                height: 350
            },
            colors: ['#4F46E5', '#6366F1', '#818CF8', '#93C5FD']
        }
    }
};

// Funciones para cargar datos
async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        if (!response.ok) throw new Error('Error al cargar estadísticas');
        const data = await response.json();
        
        updateStats(data);
    } catch (error) {
        console.error('Error:', error);
        showError('Error al cargar estadísticas');
    }
}

async function loadChartData() {
    try {
        const response = await fetch('/api/chart_data');
        if (!response.ok) throw new Error('Error al cargar datos de gráficos');
        const data = await response.json();
        
        updateCharts(data);
    } catch (error) {
        console.error('Error:', error);
        showError('Error al cargar gráficos');
    }
}

async function loadRecentActivity() {
    try {
        const response = await fetch('/api/recent_activity');
        if (!response.ok) throw new Error('Error al cargar actividad reciente');
        const data = await response.json();
        
        updateActivity(data);
    } catch (error) {
        console.error('Error:', error);
        showError('Error al cargar actividad reciente');
    }
}

// Funciones de actualización de UI
function updateStats(data) {
    document.querySelectorAll('[data-stat]').forEach(element => {
        const stat = element.dataset.stat;
        const value = data[stat];
        
        if (stat === 'ventas') {
            element.textContent = formatCurrency(value);
        } else {
            element.textContent = formatNumber(value);
        }
    });
}

function updateCharts(data) {
    // Actualizar gráfico mensual
    if (data.monthly_data) {
        const monthlyChart = new ApexCharts(
            document.querySelector("#monthly-chart"), 
            {
                ...chartConfig.monthlyChart.options,
                series: [{
                    name: 'Cotizaciones',
                    data: data.monthly_data.map(d => d.cotizaciones)
                }, {
                    name: 'Facturas',
                    data: data.monthly_data.map(d => d.facturas)
                }],
                xaxis: {
                    categories: data.monthly_data.map(d => d.mes)
                }
            }
        );
        monthlyChart.render();
    }

    // Actualizar gráfico regional
    if (data.regional_data) {
        const regionalChart = new ApexCharts(
            document.querySelector("#regional-chart"),
            {
                ...chartConfig.regionalChart.options,
                series: data.regional_data.map(d => d.total),
                labels: data.regional_data.map(d => d.ubicacion)
            }
        );
        regionalChart.render();
    }
}

function updateActivity(data) {
    const activityContainer = document.querySelector('#recent-activity');
    activityContainer.innerHTML = data.activities.map(activity => `
        <li class="px-4 py-4 sm:px-6">
            <div class="flex items-center space-x-4">
                <div class="flex-shrink-0">
                    <i class="fas ${activity.icon} text-indigo-600"></i>
                </div>
                <div class="flex-1 min-w-0">
                    <p class="text-sm font-medium text-gray-900">${activity.description}</p>
                    <p class="text-sm text-gray-500">${formatDate(activity.timestamp)}</p>
                </div>
            </div>
        </li>
    `).join('');
}

// Funciones de utilidad
function formatCurrency(value) {
    return new Intl.NumberFormat('es-PA', {
        style: 'currency',
        currency: 'USD'
    }).format(value);
}

function formatNumber(value) {
    return new Intl.NumberFormat('es-PA').format(value);
}

function formatDate(dateString) {
    return new Date(dateString).toLocaleDateString('es-PA', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function showError(message) {
    // Implementar manejo de errores UI
    console.error(message);
}

// Inicialización
document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadChartData();
    loadRecentActivity();

    // Refrescar datos cada 5 minutos
    setInterval(() => {
        loadStats();
        loadChartData();
        loadRecentActivity();
    }, 300000);
});