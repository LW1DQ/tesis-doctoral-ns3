#include "ns3/core-module.h"
#include "ns3/network-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/wifi-module.h"
#include "ns3/aodv-module.h"
#include "ns3/olsr-module.h"
#include "ns3/dsdv-module.h"
#include "ns3/dsr-module.h"
#include "ns3/applications-module.h"
#include "ns3/flow-monitor-module.h"
#include "ns3/energy-module.h"
#include <fstream>
#include <iomanip>
#include <ctime>
#include <sys/stat.h>
#include <map>
#include <vector>

using namespace ns3;

NS_LOG_COMPONENT_DEFINE("IoTSimulation");

// Variables globales
static std::string g_routingProtocol;
static uint32_t g_nFixedNodes;
static uint32_t g_nMobileNodes;
static uint32_t g_nMaliciousNodes;
static uint32_t g_nInterferingNodes;
static std::string g_configName;
static uint16_t g_normalPort = 9;
static uint16_t g_maliciousPort = 10;
static std::map<uint32_t, std::vector<double>> g_nodeMetrics; // Para métricas de nodos
static std::map<uint32_t, double> g_energyConsumed; // Para consumo de energía
static double g_simulationTime;
static std::string g_outputDir = "simulation_results";
static uint32_t g_seed = 1;

// Clase TrafficTypeTag
class TrafficTypeTag : public Tag {
public:
    static TypeId GetTypeId(void) {
        static TypeId tid = TypeId("ns3::TrafficTypeTag")
            .SetParent<Tag>()
            .AddConstructor<TrafficTypeTag>();
        return tid;
    }
    TypeId GetInstanceTypeId(void) const override { return GetTypeId(); }
    uint32_t GetSerializedSize(void) const override { return 1; }
    void Serialize(TagBuffer i) const override { i.WriteU8(trafficType); }
    void Deserialize(TagBuffer i) override { trafficType = i.ReadU8(); }
    void Print(std::ostream &os) const override { os << "TrafficType=" << (uint32_t)trafficType; }
    void SetTrafficType(uint8_t type) { trafficType = type; }
    uint8_t GetTrafficType(void) const { return trafficType; }
private:
    uint8_t trafficType; // 0: Normal, 1: Malicioso, 2: Interferente
};

// Clase PacketLogger
class PacketLogger
{
public:
    static void LogNormalPacket(Ptr<const Packet> packet, const Address &from) {
        LogPacketDetails(packet, from, g_normalPort, "normal");
    }
    static void LogMaliciousPacket(Ptr<const Packet> packet, const Address &from) {
        LogPacketDetails(packet, from, g_maliciousPort, "malicious");
    }
private:
    static void LogPacketDetails(Ptr<const Packet> packet, const Address &from, uint16_t port, 
                                const std::string &sinkType) {
        if (!packet) { NS_LOG_ERROR("Paquete nulo en LogPacketDetails"); return; }
        TrafficTypeTag tag;
        uint8_t trafficType = 0;
        if (packet->PeekPacketTag(tag)) trafficType = tag.GetTrafficType();
        std::string trafficLabel = trafficType == 0 ? "Normal" : trafficType == 1 ? "Malicioso" : "Interferente";
        std::string packetLogDir = g_outputDir + "/packet_logs";
        mkdir(g_outputDir.c_str(), 0777);
        mkdir(packetLogDir.c_str(), 0777);
        std::string packetLogFile = packetLogDir + "/packets_" + sinkType + ".csv";
        static std::map<std::string, bool> headerWritten;
        std::ofstream packetLog(packetLogFile, std::ios::app);
        if (!packetLog.is_open()) { NS_LOG_ERROR("No se pudo abrir " << packetLogFile); return; }
        if (!headerWritten[packetLogFile]) { 
            packetLog << "timestamp,source_ip,port,traffic_type,packet_size,sim_time\n"; 
            headerWritten[packetLogFile] = true; 
        }
        std::time_t now = std::time(nullptr);
        char timestamp[100];
        std::strftime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S", std::localtime(&now));
        InetSocketAddress inetAddr = InetSocketAddress::ConvertFrom(from);
        Ipv4Address srcAddr = inetAddr.GetIpv4();
        packetLog << timestamp << "," << srcAddr << "," << port << "," << trafficLabel << "," 
                  << packet->GetSize() << "," << Simulator::Now().GetSeconds() << "\n";
        packetLog.close();
    }
};

// Clase RoutingLogger
class RoutingLogger {
public:
    static void LogControlMessage(std::string protocol, uint32_t nodeId, 
                                 std::string msgType, uint32_t size) {
        std::string logDir = g_outputDir + "/routing_logs";
        mkdir(g_outputDir.c_str(), 0777);
        mkdir(logDir.c_str(), 0777);
        std::string logFile = logDir + "/control_messages.csv";
        static bool headerWritten = false;
        std::ofstream log(logFile, std::ios::app);
        if (!log.is_open()) { NS_LOG_ERROR("No se pudo abrir " << logFile); return; }
        if (!headerWritten) {
            log << "timestamp,protocolo,nodo_id,tipo_mensaje,tamaño\n";
            headerWritten = true;
        }
        std::time_t now = std::time(nullptr);
        char timestamp[100];
        std::strftime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S", 
                      std::localtime(&now));
        log << timestamp << "," << protocol << "," << nodeId << "," 
            << msgType << "," << size << "\n";
        log.close();
    }
};

// Función para registrar métricas temporales
void RecordTemporalMetrics(NodeContainer &allNodes, Ptr<FlowMonitor> monitor, double interval) {
    NS_LOG_DEBUG("Registrando métricas temporales en tiempo " << Simulator::Now().GetSeconds());
    if (!monitor) { NS_LOG_ERROR("FlowMonitor nulo en RecordTemporalMetrics"); return; }
    monitor->CheckForLostPackets();
    FlowMonitor::FlowStatsContainer stats = monitor->GetFlowStats();
    
    for (uint32_t i = 0; i < allNodes.GetN(); i++) {
        Ptr<Node> node = allNodes.Get(i);
        if (!node) { NS_LOG_ERROR("Nodo " << i << " nulo en RecordTemporalMetrics"); continue; }
        uint32_t nodeId = node->GetId();
        double throughput = 0.0, delay = 0.0, jitter = 0.0;
        uint32_t flowCount = 0;
        
        for (auto const& stat : stats) {
            throughput += stat.second.rxBytes * 8.0 / interval / 1000;
            delay += stat.second.delaySum.GetSeconds();
            jitter += stat.second.jitterSum.GetSeconds();
            flowCount++;
        }
        
        // Inicializar vector de métricas si está vacío
        if (g_nodeMetrics[nodeId].empty()) {
            g_nodeMetrics[nodeId].resize(3, 0.0); // throughput, delay, jitter
        }
        g_nodeMetrics[nodeId][0] = throughput / (flowCount > 0 ? flowCount : 1);
        g_nodeMetrics[nodeId][1] = delay / (flowCount > 0 ? flowCount : 1);
        g_nodeMetrics[nodeId][2] = jitter / (flowCount > 0 ? flowCount : 1);
    }
    Simulator::Schedule(Seconds(interval), &RecordTemporalMetrics, allNodes, monitor, interval);
}

// Función para registrar consumo de energía
void RecordEnergy(NodeContainer &allNodes) {
    NS_LOG_DEBUG("Registrando consumo de energía en tiempo " << Simulator::Now().GetSeconds());
    for (uint32_t i = 0; i < allNodes.GetN(); i++) {
        Ptr<Node> node = allNodes.Get(i);
        if (!node) { NS_LOG_ERROR("Nodo " << i << " nulo en RecordEnergy"); continue; }
        Ptr<ns3::energy::BasicEnergySource> source = node->GetObject<ns3::energy::BasicEnergySource>();
        if (source) g_energyConsumed[node->GetId()] = source->GetRemainingEnergy();
    }
}

// Función para registrar posiciones de nodos móviles
void LogMobilePositions(NodeContainer &mobileNodes) {
    NS_LOG_DEBUG("Registrando posiciones móviles en tiempo " << Simulator::Now().GetSeconds());
    std::string logFile = g_outputDir + "/mobile_positions.csv";
    mkdir(g_outputDir.c_str(), 0777);
    static bool headerWritten = false;
    std::ofstream log(logFile, std::ios::app);
    if (!log.is_open()) { NS_LOG_ERROR("No se pudo abrir " << logFile); return; }
    if (!headerWritten) { log << "time,node_id,x,y,z\n"; headerWritten = true; }
    double now = Simulator::Now().GetSeconds();
    for (uint32_t i = 0; i < mobileNodes.GetN(); ++i) {
        Ptr<Node> node = mobileNodes.Get(i);
        if (!node) { NS_LOG_ERROR("Nodo móvil " << i << " nulo en LogMobilePositions"); continue; }
        Ptr<MobilityModel> mobility = node->GetObject<MobilityModel>();
        if (mobility) {
            Vector pos = mobility->GetPosition();
            log << now << "," << node->GetId() << "," << pos.x << "," << pos.y << "," << pos.z << "\n";
        }
    }
    log.close();
    Simulator::Schedule(Seconds(1.0), &LogMobilePositions, mobileNodes);
}

// Función para registrar consumo de energía a lo largo del tiempo
void LogEnergyConsumption(NodeContainer &allNodes) {
    NS_LOG_DEBUG("Registrando consumo de energía en tiempo " << Simulator::Now().GetSeconds());
    std::string logFile = g_outputDir + "/energy_consumption.csv";
    mkdir(g_outputDir.c_str(), 0777);
    static bool headerWritten = false;
    std::ofstream log(logFile, std::ios::app);
    if (!log.is_open()) { NS_LOG_ERROR("No se pudo abrir " << logFile); return; }
    if (!headerWritten) { log << "time,node_id,energy_remaining\n"; headerWritten = true; }
    double now = Simulator::Now().GetSeconds();
    for (uint32_t i = 0; i < allNodes.GetN(); ++i) {
        Ptr<Node> node = allNodes.Get(i);
        if (!node) { NS_LOG_ERROR("Nodo " << i << " nulo en LogEnergyConsumption"); continue; }
        Ptr<ns3::energy::BasicEnergySource> source = node->GetObject<ns3::energy::BasicEnergySource>();
        if (source) {
            double energy = source->GetRemainingEnergy();
            log << now << "," << node->GetId() << "," << energy << "\n";
        }
    }
    log.close();
    Simulator::Schedule(Seconds(1.0), &LogEnergyConsumption, allNodes);
}

// Función para registrar metadatos de nodos
static void LogNodeMetadata(NodeContainer &fixedNodes, NodeContainer &mobileNodes, 
                           NodeContainer &maliciousNodes, NodeContainer &interferingNodes, 
                           Ipv4InterfaceContainer &interfaces) {
    NS_LOG_INFO("Registrando metadatos de nodos");
    std::string nodeLogDir = g_outputDir + "/node_metadata";
    mkdir(g_outputDir.c_str(), 0777);
    mkdir(nodeLogDir.c_str(), 0777);
    std::string nodeLogFile = nodeLogDir + "/nodes.csv";
    std::ofstream nodeLog(nodeLogFile);
    if (!nodeLog.is_open()) { NS_LOG_ERROR("No se pudo abrir " << nodeLogFile); return; }
    nodeLog << "node_id,ip_address,node_type\n";
    uint32_t offset = 0;
    for (uint32_t i = 0; i < fixedNodes.GetN(); ++i) {
        if (i >= interfaces.GetN()) { NS_LOG_ERROR("Índice de interfaz inválido para nodo fijo " << i); continue; }
        nodeLog << fixedNodes.Get(i)->GetId() << "," << interfaces.GetAddress(i) << ",Fijo\n";
    }
    offset += fixedNodes.GetN();
    for (uint32_t i = 0; i < mobileNodes.GetN(); ++i) {
        if (i + offset >= interfaces.GetN()) { NS_LOG_ERROR("Índice de interfaz inválido para nodo móvil " << i); continue; }
        nodeLog << mobileNodes.Get(i)->GetId() << "," << interfaces.GetAddress(i + offset) << ",Móvil\n";
    }
    offset += mobileNodes.GetN();
    for (uint32_t i = 0; i < maliciousNodes.GetN(); ++i) {
        if (i + offset >= interfaces.GetN()) { NS_LOG_ERROR("Índice de interfaz inválido para nodo malicioso " << i); continue; }
        nodeLog << maliciousNodes.Get(i)->GetId() << "," << interfaces.GetAddress(i + offset) << ",Malicioso\n";
    }
    offset += maliciousNodes.GetN();
    for (uint32_t i = 0; i < interferingNodes.GetN(); ++i) {
        if (i + offset >= interfaces.GetN()) { NS_LOG_ERROR("Índice de interfaz inválido para nodo interferente " << i); continue; }
        nodeLog << interferingNodes.Get(i)->GetId() << "," << interfaces.GetAddress(i + offset) << ",Interferente\n";
    }
    nodeLog.close();
    NS_LOG_INFO("Metadatos de nodos guardados en: " << nodeLogFile);
}

// Función para registrar metadatos de la simulación
static void LogSimulationMetadata() {
    NS_LOG_INFO("Registrando metadatos de simulación");
    std::string metadataFile = g_outputDir + "/metadata.txt";
    mkdir(g_outputDir.c_str(), 0777);
    std::ofstream metadataLog(metadataFile);
    if (!metadataLog.is_open()) { NS_LOG_ERROR("No se pudo abrir " << metadataFile); return; }
    std::time_t now = std::time(nullptr);
    char timestamp[100];
    std::strftime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S", std::localtime(&now));
    metadataLog << "Metadatos de Simulación\n";
    metadataLog << "Timestamp: " << timestamp << "\n";
    metadataLog << "Nodos Fijos: " << g_nFixedNodes << "\n";
    metadataLog << "Nodos Móviles: " << g_nMobileNodes << "\n";
    metadataLog << "Nodos Maliciosos: " << g_nMaliciousNodes << "\n";
    metadataLog << "Nodos Interferentes: " << g_nInterferingNodes << "\n";
    metadataLog << "Tiempo de Simulación: " << g_simulationTime << " segundos\n";
    metadataLog << "Protocolo de Enrutamiento: " << g_routingProtocol << "\n";
    metadataLog << "Nombre de Configuración: " << g_configName << "\n";
    metadataLog << "Semilla Aleatoria: " << g_seed << "\n";
    metadataLog.close();
    NS_LOG_INFO("Metadatos de simulación guardados en: " << metadataFile);
}

// Función para registrar cambios en la tabla de enrutamiento
static void LogRoutingTableChanges(NodeContainer &allNodes) {
    NS_LOG_INFO("Iniciando LogRoutingTableChanges en tiempo " << Simulator::Now().GetSeconds());
    
    // Crear directorios necesarios
    if (mkdir(g_outputDir.c_str(), 0777) != 0 && errno != EEXIST) {
        NS_LOG_ERROR("Error al crear directorio " << g_outputDir << ": " << strerror(errno));
        return;
    }
    std::string routingLogDir = g_outputDir + "/routing_logs";
    if (mkdir(routingLogDir.c_str(), 0777) != 0 && errno != EEXIST) {
        NS_LOG_ERROR("Error al crear directorio " << routingLogDir << ": " << strerror(errno));
        return;
    }

    // Crear y escribir en el archivo
    std::string routingLogFile = routingLogDir + "/routing_table_changes.csv";
    NS_LOG_INFO("Intentando escribir en archivo: " << routingLogFile);
    
    std::ofstream routingLog(routingLogFile, std::ios::app);
    if (!routingLog.is_open()) {
        NS_LOG_ERROR("No se pudo abrir " << routingLogFile << ": " << strerror(errno));
        return;
    }

    static bool headerWritten = false;
    if (!headerWritten) {
        routingLog << "timestamp,node_id,protocol,destination,next_hop,metric\n";
        headerWritten = true;
        NS_LOG_INFO("Encabezado escrito en " << routingLogFile);
    }

    double now = Simulator::Now().GetSeconds();
    uint32_t nodesProcessed = 0;

    for (uint32_t i = 0; i < allNodes.GetN(); ++i) {
        Ptr<Node> node = allNodes.Get(i);
        if (!node) {
            NS_LOG_ERROR("Nodo " << i << " es nulo");
            continue;
        }

        Ptr<Ipv4> ipv4 = node->GetObject<Ipv4>();
        if (!ipv4) {
            NS_LOG_ERROR("No se pudo obtener Ipv4 para nodo " << i);
            continue;
        }

        Ptr<Ipv4RoutingProtocol> routing = ipv4->GetRoutingProtocol();
        if (!routing) {
            NS_LOG_ERROR("No se pudo obtener protocolo de enrutamiento para nodo " << i);
            continue;
        }

        bool entryWritten = false;
        if (g_routingProtocol == "AODV") {
            Ptr<aodv::RoutingProtocol> aodv = DynamicCast<aodv::RoutingProtocol>(routing);
            if (aodv) {
                routingLog << now << "," << node->GetId() << ",AODV,0.0.0.0,0.0.0.0,0\n";
                entryWritten = true;
            }
        } else if (g_routingProtocol == "OLSR") {
            Ptr<olsr::RoutingProtocol> olsr = DynamicCast<olsr::RoutingProtocol>(routing);
            if (olsr) {
                routingLog << now << "," << node->GetId() << ",OLSR,0.0.0.0,0.0.0.0,0\n";
                entryWritten = true;
            }
        } else if (g_routingProtocol == "DSDV") {
            Ptr<dsdv::RoutingProtocol> dsdv = DynamicCast<dsdv::RoutingProtocol>(routing);
            if (dsdv) {
                routingLog << now << "," << node->GetId() << ",DSDV,0.0.0.0,0.0.0.0,0\n";
                entryWritten = true;
            }
        } else if (g_routingProtocol == "DSR") {
            Ptr<dsr::DsrRouting> dsr = DynamicCast<dsr::DsrRouting>(routing);
            if (dsr) {
                routingLog << now << "," << node->GetId() << ",DSR,0.0.0.0,0.0.0.0,0\n";
                entryWritten = true;
            }
        }

        if (entryWritten) {
            nodesProcessed++;
        }
    }

    routingLog.close();
    NS_LOG_INFO("LogRoutingTableChanges completado. Nodos procesados: " << nodesProcessed);
    
    // Programar la próxima ejecución solo si no hemos llegado al final de la simulación
    if (Simulator::Now().GetSeconds() < g_simulationTime - 1.0) {
        Simulator::Schedule(Seconds(1.0), &LogRoutingTableChanges, allNodes);
    }
}

// Función para calcular métricas
static void CalculateMetrics(Ptr<FlowMonitor> monitor, double simTime) {
    NS_LOG_INFO("Iniciando cálculo de métricas...");
    if (!monitor) { 
        NS_LOG_ERROR("FlowMonitor no está inicializado"); 
        return; 
    }

    // Crear directorios necesarios
    if (mkdir(g_outputDir.c_str(), 0777) != 0 && errno != EEXIST) {
        NS_LOG_ERROR("Error al crear directorio " << g_outputDir << ": " << strerror(errno));
        return;
    }
    std::string metricsDir = g_outputDir + "/metrics";
    if (mkdir(metricsDir.c_str(), 0777) != 0 && errno != EEXIST) {
        NS_LOG_ERROR("Error al crear directorio " << metricsDir << ": " << strerror(errno));
        return;
    }

    monitor->CheckForLostPackets();
    FlowMonitor::FlowStatsContainer stats = monitor->GetFlowStats();
    NS_LOG_INFO("Número de flujos detectados: " << stats.size());

    // Generar metrics.csv
    std::string csvFileName = metricsDir + "/metrics.csv";
    NS_LOG_INFO("Intentando escribir en archivo: " << csvFileName);
    
    std::ofstream csvFile(csvFileName, std::ios::out | std::ios::trunc);
    if (!csvFile.is_open()) { 
        NS_LOG_ERROR("No se pudo abrir " << csvFileName << ": " << strerror(errno)); 
        return; 
    }

    csvFile << "timestamp,protocolo,nodos_fijos,nodos_moviles,nodos_maliciosos,nodos_interferentes,"
            << "throughput_promedio,throughput_maximo,delay_promedio,delay_maximo,delay_minimo,"
            << "jitter_promedio,perdida_paquetes,pdr,paquetes_totales,paquetes_perdidos,"
            << "numero_flujos,tiempo_simulacion\n";

    double totalThroughput = 0.0, totalDelay = 0.0, totalJitter = 0.0;
    uint64_t totalPackets = 0, lostPackets = 0;
    uint32_t flowCount = 0;
    double maxDelay = 0.0, minDelay = std::numeric_limits<double>::max();
    double pdr = 0.0;

    for (auto const& stat : stats) {
        double flowThroughput = stat.second.rxBytes * 8.0 / simTime / 1000;
        totalThroughput += flowThroughput;
        double flowDelay = stat.second.delaySum.GetSeconds();
        totalDelay += flowDelay;
        maxDelay = std::max(maxDelay, flowDelay);
        if (stat.second.rxPackets > 0) minDelay = std::min(minDelay, flowDelay / stat.second.rxPackets);
        totalJitter += stat.second.jitterSum.GetSeconds();
        totalPackets += stat.second.txPackets;
        lostPackets += stat.second.lostPackets;
        flowCount++;
    }

    double avgThroughput = flowCount > 0 ? totalThroughput / flowCount : 0.0;
    double avgDelay = flowCount > 0 ? totalDelay / flowCount : 0.0;
    double avgJitter = flowCount > 0 ? totalJitter / flowCount : 0.0;
    double packetLossRatio = totalPackets > 0 ? (double)lostPackets / totalPackets * 100.0 : 0.0;
    pdr = totalPackets > 0 ? (double)(totalPackets - lostPackets) / totalPackets * 100.0 : 0.0;

    std::time_t now = std::time(nullptr);
    char timestamp[100];
    std::strftime(timestamp, sizeof(timestamp), "%Y-%m-%d %H:%M:%S", std::localtime(&now));

    csvFile << timestamp << "," << g_routingProtocol << "," << g_nFixedNodes << "," << g_nMobileNodes << "," 
            << g_nMaliciousNodes << "," << g_nInterferingNodes << "," << std::fixed << std::setprecision(6)
            << avgThroughput << "," << totalThroughput << "," << avgDelay << "," << maxDelay << "," 
            << (minDelay == std::numeric_limits<double>::max() ? 0 : minDelay) << "," << avgJitter << "," 
            << packetLossRatio << "," << pdr << "," << totalPackets << "," << lostPackets << "," 
            << flowCount << "," << simTime << "\n";

    csvFile.close();
    NS_LOG_INFO("Archivo metrics.csv creado exitosamente");

    // Guardar métricas de nodos
    std::string nodeMetricsFile = metricsDir + "/node_metrics.csv";
    std::ofstream nodeMetrics(nodeMetricsFile, std::ios::out | std::ios::trunc);
    if (!nodeMetrics.is_open()) { 
        NS_LOG_ERROR("No se pudo abrir " << nodeMetricsFile << ": " << strerror(errno)); 
        return; 
    }
    nodeMetrics << "node_id,throughput_avg,delay_avg,jitter_avg,energy_consumed\n";
    for (auto const& entry : g_nodeMetrics) {
        uint32_t nodeId = entry.first;
        std::vector<double> metrics = entry.second;
        double throughputAvg = metrics.size() > 0 ? metrics[0] : 0.0;
        double delayAvg = metrics.size() > 1 ? metrics[1] : 0.0;
        double jitterAvg = metrics.size() > 2 ? metrics[2] : 0.0;
        double energy = g_energyConsumed[nodeId];
        nodeMetrics << nodeId << "," << throughputAvg << "," << delayAvg << "," << jitterAvg << "," << energy << "\n";
    }
    nodeMetrics.close();
    NS_LOG_INFO("Archivo node_metrics.csv creado exitosamente");
}

int main(int argc, char *argv[]) {
    uint32_t nFixedNodes = 20, nMobileNodes = 10, nMaliciousNodes = 0, nInterferingNodes = 0;
    std::string pcapPrefix = "iot_simulation", routingProtocol = "AODV", configName = "mal_int";
    double simTime = 60.0, interval = 2.0, maliciousInterval = 0.01;
    uint32_t packetSize = 512;
    std::string outputDir = "simulation_results";
    uint32_t seed = 1;

    CommandLine cmd;
    cmd.AddValue("nFixedNodes", "Número de nodos IoT fijos", nFixedNodes);
    cmd.AddValue("nMobileNodes", "Número de nodos IoT móviles", nMobileNodes);
    cmd.AddValue("nMaliciousNodes", "Número de nodos maliciosos", nMaliciousNodes);
    cmd.AddValue("nInterferingNodes", "Número de nodos interferentes", nInterferingNodes);
    cmd.AddValue("simTime", "Tiempo de simulación en segundos", simTime);
    cmd.AddValue("routingProtocol", "Protocolo de enrutamiento (AODV, OLSR, DSDV, DSR)", routingProtocol);
    cmd.AddValue("configName", "Nombre de configuración", configName);
    cmd.AddValue("outputDir", "Directorio de salida para resultados", outputDir);
    cmd.AddValue("seed", "Semilla aleatoria para simulación", seed);
    cmd.Parse(argc, argv);

    // Establecer variables globales
    g_nFixedNodes = nFixedNodes;
    g_nMobileNodes = nMobileNodes;
    g_nMaliciousNodes = nMaliciousNodes;
    g_nInterferingNodes = nInterferingNodes;
    g_simulationTime = simTime;
    g_routingProtocol = routingProtocol;
    g_configName = configName;
    g_outputDir = outputDir;
    g_seed = seed;

    // Establecer semilla aleatoria
    RngSeedManager::SetSeed(seed);

    LogComponentEnable("IoTSimulation", LOG_LEVEL_ALL);
    if (routingProtocol == "DSR") LogComponentEnable("DsrRouting", LOG_LEVEL_ALL);

    NS_LOG_INFO("=== Iniciando simulación ===");
    NS_LOG_INFO("Protocolo: " << routingProtocol);
    NS_LOG_INFO("Configuración: " << configName);
    NS_LOG_INFO("Nodos fijos: " << nFixedNodes);
    NS_LOG_INFO("Nodos móviles: " << nMobileNodes);
    NS_LOG_INFO("Nodos maliciosos: " << nMaliciousNodes);
    NS_LOG_INFO("Nodos interferentes: " << nInterferingNodes);
    NS_LOG_INFO("Directorio de salida: " << outputDir);
    NS_LOG_INFO("Semilla: " << seed);
    NS_LOG_INFO("==========================");

    NodeContainer fixedNodes, mobileNodes, maliciousNodes, interferingNodes;
    fixedNodes.Create(nFixedNodes);
    mobileNodes.Create(nMobileNodes);
    maliciousNodes.Create(nMaliciousNodes);
    interferingNodes.Create(nInterferingNodes);
    NodeContainer allNodes;
    allNodes.Add(fixedNodes);
    allNodes.Add(mobileNodes);
    allNodes.Add(maliciousNodes);
    allNodes.Add(interferingNodes);
    NS_LOG_INFO("Total de nodos creados: " << allNodes.GetN());
    if (allNodes.GetN() == 0) { NS_LOG_ERROR("No se crearon nodos, abortando simulación"); return 1; }

    WifiHelper wifi;
    wifi.SetStandard(WIFI_STANDARD_80211g);
    wifi.SetRemoteStationManager("ns3::IdealWifiManager");

    YansWifiPhyHelper wifiPhy;
    YansWifiChannelHelper wifiChannel = YansWifiChannelHelper::Default();
    wifiPhy.SetChannel(wifiChannel.Create());
    wifiPhy.Set("RxSensitivity", DoubleValue(-80.0));
    wifiPhy.Set("TxPowerStart", DoubleValue(23.0));
    wifiPhy.Set("TxPowerEnd", DoubleValue(23.0));
    wifiPhy.SetErrorRateModel("ns3::NistErrorRateModel");

    WifiMacHelper wifiMac;
    wifiMac.SetType("ns3::AdhocWifiMac");
    NetDeviceContainer fixedDevices = wifi.Install(wifiPhy, wifiMac, fixedNodes);
    NetDeviceContainer mobileDevices = wifi.Install(wifiPhy, wifiMac, mobileNodes);
    NetDeviceContainer maliciousDevices = wifi.Install(wifiPhy, wifiMac, maliciousNodes);
    NetDeviceContainer interferingDevices = wifi.Install(wifiPhy, wifiMac, interferingNodes);
    NetDeviceContainer allDevices;
    allDevices.Add(fixedDevices);
    allDevices.Add(mobileDevices);
    allDevices.Add(maliciousDevices);
    allDevices.Add(interferingDevices);
    NS_LOG_INFO("Total de dispositivos creados: " << allDevices.GetN());
    if (allDevices.GetN() == 0) { NS_LOG_ERROR("No se crearon dispositivos, abortando simulación"); return 1; }

    MobilityHelper mobility;
    mobility.SetPositionAllocator("ns3::GridPositionAllocator", "MinX", DoubleValue(0.0), "MinY", DoubleValue(0.0),
                                 "DeltaX", DoubleValue(15.0), "DeltaY", DoubleValue(15.0), "GridWidth", UintegerValue(5));
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(fixedNodes);

    mobility.SetPositionAllocator("ns3::RandomRectanglePositionAllocator", 
                                 "X", StringValue("ns3::UniformRandomVariable[Min=0|Max=100]"),
                                 "Y", StringValue("ns3::UniformRandomVariable[Min=0|Max=100]"));
    mobility.SetMobilityModel("ns3::RandomWalk2dMobilityModel", 
                             "Bounds", RectangleValue(Rectangle(0, 100, 0, 100)),
                             "Speed", StringValue("ns3::ConstantRandomVariable[Constant=1.0]"),
                             "Mode", StringValue("Time"),
                             "Time", StringValue("2.0"));
    mobility.Install(mobileNodes);

    mobility.SetPositionAllocator("ns3::RandomRectanglePositionAllocator", 
                                 "X", StringValue("ns3::UniformRandomVariable[Min=60|Max=90]"),
                                 "Y", StringValue("ns3::UniformRandomVariable[Min=60|Max=90]"));
    mobility.SetMobilityModel("ns3::RandomWalk2dMobilityModel", 
                             "Bounds", RectangleValue(Rectangle(60, 90, 60, 90)),
                             "Speed", StringValue("ns3::ConstantRandomVariable[Constant=1.0]"),
                             "Mode", StringValue("Time"),
                             "Time", StringValue("2.0"));
    mobility.Install(maliciousNodes);

    mobility.SetPositionAllocator("ns3::RandomRectanglePositionAllocator", 
                                 "X", StringValue("ns3::UniformRandomVariable[Min=120|Max=150]"),
                                 "Y", StringValue("ns3::UniformRandomVariable[Min=120|Max=150]"));
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(interferingNodes);
    NS_LOG_INFO("Configuración de movilidad completada");

    BasicEnergySourceHelper energySourceHelper;
    energySourceHelper.Set("BasicEnergySourceInitialEnergyJ", DoubleValue(100.0));
    ns3::energy::EnergySourceContainer energySources = energySourceHelper.Install(allNodes);
    WifiRadioEnergyModelHelper radioEnergyHelper;
    ns3::energy::DeviceEnergyModelContainer deviceEnergyModels = radioEnergyHelper.Install(allDevices, energySources);
    NS_LOG_INFO("Configuración de energía completada");

    InternetStackHelper internet;
    if (routingProtocol == "AODV") {
        AodvHelper aodv;
        internet.SetRoutingHelper(aodv);
        internet.Install(allNodes);
    } else if (routingProtocol == "OLSR") {
        OlsrHelper olsr;
        internet.SetRoutingHelper(olsr);
        internet.Install(allNodes);
    } else if (routingProtocol == "DSDV") {
        DsdvHelper dsdv;
        internet.SetRoutingHelper(dsdv);
        internet.Install(allNodes);
    } else if (routingProtocol == "DSR") {
        DsrHelper dsr;
        internet.Install(allNodes);
        DsrMainHelper dsrMain;
        dsrMain.Install(dsr, allNodes);
    } else { NS_LOG_ERROR("Protocolo no soportado: " << routingProtocol); return 1; }

    NS_LOG_INFO("Asignando direcciones IP");
    Ipv4AddressHelper ipv4;
    ipv4.SetBase("192.168.1.0", "255.255.255.0");
    Ipv4InterfaceContainer interfaces = ipv4.Assign(allDevices);
    LogNodeMetadata(fixedNodes, mobileNodes, maliciousNodes, interferingNodes, interfaces);
    NS_LOG_INFO("Direcciones IP asignadas");

    LogSimulationMetadata();

    NS_LOG_INFO("Configurando aplicaciones de tráfico normal");
    OnOffHelper normalOnOff("ns3::UdpSocketFactory", Address(InetSocketAddress(interfaces.GetAddress(0), g_normalPort)));
    normalOnOff.SetConstantRate(DataRate(std::to_string(packetSize * 8 / interval) + "bps"), packetSize);
    normalOnOff.SetAttribute("OnTime", StringValue("ns3::ConstantRandomVariable[Constant=1.0]"));
    normalOnOff.SetAttribute("OffTime", StringValue("ns3::ConstantRandomVariable[Constant=0.0]"));
    ApplicationContainer normalApps;
    for (uint32_t i = 0; i < nFixedNodes; ++i) normalApps.Add(normalOnOff.Install(fixedNodes.Get(i)));
    for (uint32_t i = 0; i < nMobileNodes; ++i) normalApps.Add(normalOnOff.Install(mobileNodes.Get(i)));
    normalApps.Start(Seconds(1.0));
    normalApps.Stop(Seconds(simTime));

    NS_LOG_INFO("Configurando aplicaciones de tráfico malicioso");
    OnOffHelper maliciousOnOff("ns3::UdpSocketFactory", Address(InetSocketAddress(interfaces.GetAddress(0), g_maliciousPort)));
    maliciousOnOff.SetConstantRate(DataRate(std::to_string(packetSize * 8 / maliciousInterval) + "bps"), packetSize);
    maliciousOnOff.SetAttribute("OnTime", StringValue("ns3::ConstantRandomVariable[Constant=1.0]"));
    maliciousOnOff.SetAttribute("OffTime", StringValue("ns3::ConstantRandomVariable[Constant=0.0]"));
    ApplicationContainer maliciousApps;
    if (nMaliciousNodes > 0) {
        for (uint32_t i = 0; i < nMaliciousNodes; ++i) maliciousApps.Add(maliciousOnOff.Install(maliciousNodes.Get(i)));
        maliciousApps.Start(Seconds(10.0));
        maliciousApps.Stop(Seconds(simTime));
    }

    NS_LOG_INFO("Configurando aplicaciones de tráfico interferente");
    OnOffHelper interferingOnOff("ns3::UdpSocketFactory", Address(InetSocketAddress(interfaces.GetAddress(0), g_normalPort)));
    interferingOnOff.SetConstantRate(DataRate(std::to_string(packetSize * 8 / interval) + "bps"), packetSize);
    interferingOnOff.SetAttribute("OnTime", StringValue("ns3::ConstantRandomVariable[Constant=1.0]"));
    interferingOnOff.SetAttribute("OffTime", StringValue("ns3::ConstantRandomVariable[Constant=0.0]"));
    ApplicationContainer interferingApps;
    if (nInterferingNodes > 0) {
        for (uint32_t i = 0; i < nInterferingNodes; ++i) interferingApps.Add(interferingOnOff.Install(interferingNodes.Get(i)));
        interferingApps.Start(Seconds(5.0));
        interferingApps.Stop(Seconds(simTime));
    }

    NS_LOG_INFO("Configurando sumideros de paquetes");
    PacketSinkHelper normalSink("ns3::UdpSocketFactory", Address(InetSocketAddress(Ipv4Address::GetAny(), g_normalPort)));
    ApplicationContainer normalSinkApp = normalSink.Install(fixedNodes.Get(0));
    normalSinkApp.Start(Seconds(0.0));
    normalSinkApp.Stop(Seconds(simTime));
    Ptr<PacketSink> sink = DynamicCast<PacketSink>(normalSinkApp.Get(0));
    if (!sink) { NS_LOG_ERROR("Fallo al crear sumidero de paquetes normal"); return 1; }
    sink->TraceConnectWithoutContext("Rx", MakeCallback(&PacketLogger::LogNormalPacket));

    PacketSinkHelper maliciousSink("ns3::UdpSocketFactory", Address(InetSocketAddress(Ipv4Address::GetAny(), g_maliciousPort)));
    ApplicationContainer maliciousSinkApp = maliciousSink.Install(fixedNodes.Get(0));
    maliciousSinkApp.Start(Seconds(0.0));
    maliciousSinkApp.Stop(Seconds(simTime));
    Ptr<PacketSink> maliciousSinkPtr = DynamicCast<PacketSink>(maliciousSinkApp.Get(0));
    if (!maliciousSinkPtr) { NS_LOG_ERROR("Fallo al crear sumidero de paquetes malicioso"); return 1; }
    maliciousSinkPtr->TraceConnectWithoutContext("Rx", MakeCallback(&PacketLogger::LogMaliciousPacket));

    NS_LOG_INFO("Configurando captura PCAP");
    mkdir(g_outputDir.c_str(), 0777);
    std::string pcapDir = g_outputDir + "/pcap";
    mkdir(pcapDir.c_str(), 0777);
    wifiPhy.EnablePcap(pcapPrefix + "_" + routingProtocol + "_" + std::to_string(nFixedNodes) + "f_" + 
                       std::to_string(nMobileNodes) + "m_" + std::to_string(nMaliciousNodes) + "mal_" + 
                       std::to_string(nInterferingNodes) + "i_" + configName, allDevices, false);

    NS_LOG_INFO("Instalando FlowMonitor");
    FlowMonitorHelper flowMonitor;
    Ptr<FlowMonitor> monitor = flowMonitor.Install(allNodes);
    if (!monitor) { NS_LOG_ERROR("Fallo al instalar FlowMonitor"); return 1; }
    NS_LOG_INFO("FlowMonitor instalado en " << allNodes.GetN() << " nodos");

    NS_LOG_INFO("Programando eventos de simulación");
    Simulator::Schedule(Seconds(1.0), &LogMobilePositions, mobileNodes);
    Simulator::Schedule(Seconds(1.0), &LogEnergyConsumption, allNodes);
    Simulator::Schedule(Seconds(1.0), &RecordTemporalMetrics, allNodes, monitor, 1.0);
    Simulator::Schedule(Seconds(1.0), &LogRoutingTableChanges, allNodes);
    Simulator::Schedule(Seconds(simTime - 0.1), &CalculateMetrics, monitor, simTime);
    Simulator::Schedule(Seconds(simTime - 0.1), &RecordEnergy, allNodes);
    
    NS_LOG_INFO("Iniciando simulación...");
    Simulator::Stop(Seconds(simTime));
    Simulator::Run();
    NS_LOG_INFO("Simulación completada.");
    Simulator::Destroy();
    return 0;
}