#!/usr/bin/env python3

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import logging
from typing import Dict, List
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats

class SecurityAnalyzer:
    def __init__(self, simulation_dir: str):
        self.simulation_dir = Path(simulation_dir)
        self.results_dir = Path('post_processing/results')
        self.configs = ['no_mal_no_int', 'int_no_mal', 'mal_no_int', 'mal_int']
        self.protocols = ['AODV', 'OLSR', 'DSDV', 'DSR']
        self.metrics = {
            'perdida_paquetes': 'Tasa de pérdida de paquetes',
            'delay_promedio': 'Latencia de red',
            'jitter_promedio': 'Jitter de red',
            'throughput_promedio': 'Throughput de red',
            'pdr': 'Packet Delivery Ratio'
        }
        
    def analyze_security_metrics(self, metrics_data: Dict):
        """Analiza métricas relacionadas con seguridad"""
        for metric, description in self.metrics.items():
            self._analyze_security_metric(metrics_data, metric, description)
            
    def _analyze_security_metric(self, metrics_data: Dict, metric: str, description: str):
        """Analiza una métrica específica de seguridad"""
        # Crear DataFrame para análisis
        data = []
        for config in self.configs:
            for protocol in self.protocols:
                protocol_data = metrics_data[config][protocol]
                for run_name, run_data in protocol_data.items():
                    if metric in run_data.columns:
                        # Calcular el valor promedio para esta métrica
                        values = run_data[metric].dropna().values
                        if len(values) > 0:  # Solo agregar si hay valores no-NaN
                            value = np.mean(values)
                            data.append({
                                'config': config,
                                'protocol': protocol,
                                'run': run_name,
                                'value': value
                            })
        
        if not data:  # Si no hay datos, salir
            logging.warning(f"No se encontraron datos para la métrica {metric}")
            return
            
        df = pd.DataFrame(data)
        
        # Asegurarse de que el directorio de tablas existe
        tables_dir = self.results_dir / 'tables'
        tables_dir.mkdir(parents=True, exist_ok=True)
        
        # Análisis estadístico
        stats_by_config = df.groupby('config')['value'].agg(['mean', 'std', 'min', 'max'])
        stats_by_protocol = df.groupby('protocol')['value'].agg(['mean', 'std', 'min', 'max'])
        
        # Guardar estadísticas
        stats_by_config.to_csv(str(tables_dir / f'{metric}_by_config.csv'))
        stats_by_protocol.to_csv(str(tables_dir / f'{metric}_by_protocol.csv'))
        
        # Generar gráficos
        self._plot_security_metric(df, metric, description)
        
    def _plot_security_metric(self, df: pd.DataFrame, metric: str, description: str):
        """Genera gráficos para una métrica de seguridad"""
        # Gráfico de barras por configuración
        fig = px.box(df, x='config', y='value', color='protocol',
                    title=f'{description} por Configuración y Protocolo')
        fig.write_html(str(self.results_dir / 'graphs' / f'{metric}_security.html'))
        
        # Gráfico de violín
        plt.figure(figsize=(12, 6))
        sns.violinplot(data=df, x='config', y='value', hue='protocol')
        plt.title(f'Distribución de {description}')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig(str(self.results_dir / 'graphs' / f'{metric}_violin.png'))
        plt.close()
        
    def analyze_attack_impact(self, metrics_data: Dict):
        """Analiza el impacto de los ataques en el rendimiento de la red"""
        impact_metrics = {
            'throughput_promedio': 'Impacto en el throughput',
            'delay_promedio': 'Impacto en la latencia',
            'perdida_paquetes': 'Impacto en la pérdida de paquetes',
            'pdr': 'Impacto en el PDR'
        }
        
        for metric, description in impact_metrics.items():
            self._analyze_attack_impact(metrics_data, metric, description)
            
    def _analyze_attack_impact(self, metrics_data: Dict, metric: str, description: str):
        """Analiza el impacto de ataques en una métrica específica"""
        # Comparar configuraciones con y sin ataques
        baseline = metrics_data['no_mal_no_int']
        attack_configs = ['mal_no_int', 'int_no_mal', 'mal_int']
        
        impact_data = []
        for protocol in self.protocols:
            baseline_values = []
            for run_data in baseline[protocol].values():
                if metric in run_data.columns:
                    values = run_data[metric].dropna().values
                    if len(values) > 0:
                        baseline_values.extend(values)
            
            if not baseline_values:  # Si no hay datos de línea base, continuar con el siguiente protocolo
                logging.warning(f"No se encontraron datos de línea base para {metric} en {protocol}")
                continue
                
            baseline_mean = np.mean(baseline_values)
            if baseline_mean == 0:  # Evitar división por cero
                logging.warning(f"Valor base cero para {metric} en {protocol}, saltando cálculo de impacto")
                continue
            
            for config in attack_configs:
                attack_values = []
                for run_data in metrics_data[config][protocol].values():
                    if metric in run_data.columns:
                        values = run_data[metric].dropna().values
                        if len(values) > 0:
                            attack_values.extend(values)
                
                if not attack_values:  # Si no hay datos de ataque, continuar con la siguiente configuración
                    logging.warning(f"No se encontraron datos de ataque para {metric} en {protocol} con {config}")
                    continue
                    
                attack_mean = np.mean(attack_values)
                try:
                    impact = ((attack_mean - baseline_mean) / baseline_mean) * 100
                    if not np.isnan(impact) and not np.isinf(impact):
                        impact_data.append({
                            'protocol': protocol,
                            'config': config,
                            'impact': impact
                        })
                except (ZeroDivisionError, ValueError) as e:
                    logging.warning(f"Error al calcular impacto para {metric} en {protocol} con {config}: {str(e)}")
                    continue
        
        if not impact_data:  # Si no hay datos de impacto, salir
            logging.warning(f"No se encontraron datos de impacto para la métrica {metric}")
            return
            
        df = pd.DataFrame(impact_data)
        
        # Asegurarse de que el directorio de tablas existe
        tables_dir = self.results_dir / 'tables'
        tables_dir.mkdir(parents=True, exist_ok=True)
        
        # Guardar resultados
        df.to_csv(str(tables_dir / f'{metric}_attack_impact.csv'), index=False)
        
        # Generar gráfico
        fig = px.bar(df, x='protocol', y='impact', color='config',
                    title=f'{description} por Protocolo y Tipo de Ataque',
                    barmode='group')
        fig.write_html(str(self.results_dir / 'graphs' / f'{metric}_attack_impact.html'))
        
    def generate_security_report(self, metrics_data: Dict):
        """Genera un reporte de seguridad"""
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
        
        # Asegurarse de que el directorio de reportes existe
        reports_dir = self.results_dir / 'reports'
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        # Convertir Path a string para el nombre del archivo
        pdf_path = str(reports_dir / 'security_report.pdf')
        
        doc = SimpleDocTemplate(
            pdf_path,
            pagesize=letter
        )
        styles = getSampleStyleSheet()
        elements = []
        
        # Título
        elements.append(Paragraph("Análisis de Seguridad", styles['Title']))
        elements.append(Spacer(1, 12))
        
        # Resumen de seguridad
        elements.append(Paragraph("Resumen de Seguridad", styles['Heading1']))
        elements.append(Paragraph(
            "Este reporte presenta un análisis detallado de la seguridad de la red "
            "bajo diferentes condiciones de ataque y protocolos de enrutamiento.",
            styles['Normal']
        ))
        elements.append(Spacer(1, 12))
        
        # Análisis de métricas de seguridad
        self.analyze_security_metrics(metrics_data)
        
        # Análisis de impacto de ataques
        self.analyze_attack_impact(metrics_data)
        
        # Conclusiones de seguridad
        elements.append(Paragraph("Conclusiones de Seguridad", styles['Heading1']))
        elements.append(Paragraph(
            "Basado en el análisis de los datos, se pueden extraer las siguientes conclusiones "
            "sobre la seguridad de la red:",
            styles['Normal']
        ))
        
        # Generar conclusiones automáticamente
        for metric in self.metrics.keys():
            metric_file = self.results_dir / 'tables' / f'{metric}_by_protocol.csv'
            if metric_file.exists():
                try:
                    metric_data = pd.read_csv(metric_file)
                    if not metric_data.empty:
                        best_protocol = metric_data.loc[metric_data['mean'].idxmin()]
                        elements.append(Paragraph(
                            f"• Para {self.metrics[metric]}: El protocolo {best_protocol.name} mostró la mejor resistencia "
                            f"a ataques con un valor promedio de {best_protocol['mean']:.2f}.",
                            styles['Normal']
                        ))
                except Exception as e:
                    logging.error(f"Error al procesar {metric}: {str(e)}")
                    elements.append(Paragraph(
                        f"• No se pudieron generar conclusiones para {self.metrics[metric]} debido a datos insuficientes.",
                        styles['Normal']
                    ))
            else:
                elements.append(Paragraph(
                    f"• No se encontraron datos suficientes para analizar {self.metrics[metric]}.",
                    styles['Normal']
                ))
        
        doc.build(elements)

if __name__ == "__main__":
    import sys
    from run_analysis import SimulationAnalyzer
    
    if len(sys.argv) != 2:
        print("Uso: python security_analysis.py <directorio_simulacion>")
        sys.exit(1)
    
    # Cargar datos usando el analizador principal
    analyzer = SimulationAnalyzer(sys.argv[1])
    metrics_data = analyzer.load_metrics()
    
    # Realizar análisis de seguridad
    security_analyzer = SecurityAnalyzer(sys.argv[1])
    security_analyzer.generate_security_report(metrics_data) 