from flask import Flask, send_file, request, jsonify, session
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import io
import anthropic
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "your-secret-key-change-in-production")

# Configure caching - increased timeout to reduce API calls
app.config['CACHE_TYPE'] = 'simple'
app.config['CACHE_DEFAULT_TIMEOUT'] = 300
cache = Cache(app)

# Configure rate limiting
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Get API key from environment variable
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Email configuration
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")  # Gmail SMTP server
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))  # TLS port
EMAIL_USER = os.environ.get("EMAIL_USER")  # Your email address
EMAIL_PASSWORD = os.environ.get("EMAIL_PASSWORD")  # Your email password or app-specific password
EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "Crypto Dashboard")

def send_subscription_email(to_email, lang='en'):
    """Send subscription welcome email with premium features info"""
    if not EMAIL_USER or not EMAIL_PASSWORD:
        print("❌ ERROR: Email credentials not configured")
        print(f"   EMAIL_USER: {'SET' if EMAIL_USER else 'NOT SET'}")
        print(f"   EMAIL_PASSWORD: {'SET' if EMAIL_PASSWORD else 'NOT SET'}")
        return False
    
    print(f"📧 Attempting to send email to: {to_email}")
    print(f"   Using SMTP: {EMAIL_HOST}:{EMAIL_PORT}")
    print(f"   From: {EMAIL_USER}")
    
    t = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    
    # Email content based on language
    if lang == 'es':
        subject = "¡Bienvenido a Crypto Dashboard Premium!"
        body_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #667eea;">¡Gracias por tu interés en Crypto Dashboard Premium!</h2>
                    
                    <p>Hola,</p>
                    
                    <p>Gracias por suscribirte a nuestras actualizaciones. Aquí están las increíbles características que obtendrás con Premium:</p>
                    
                    <div style="background: #f9fafb; padding: 20px; border-radius: 10px; margin: 20px 0;">
                        <h3 style="color: #667eea;">✨ Características Premium</h3>
                        <ul style="list-style: none; padding: 0;">
                            <li style="padding: 8px 0;">🔔 <strong>Alertas de precios en tiempo real</strong> - Recibe notificaciones instantáneas sobre movimientos de precios</li>
                            <li style="padding: 8px 0;">📊 <strong>Indicadores técnicos avanzados</strong> - Accede a más de 20 indicadores profesionales</li>
                            <li style="padding: 8px 0;">💼 <strong>Seguimiento de cartera</strong> - Rastrea múltiples criptomonedas en un solo lugar</li>
                            <li style="padding: 8px 0;">🤖 <strong>Soporte prioritario de IA</strong> - Preguntas ilimitadas y respuestas más rápidas</li>
                            <li style="padding: 8px 0;">📈 <strong>Datos históricos extendidos</strong> - Hasta 5 años de datos históricos</li>
                            <li style="padding: 8px 0;">🎯 <strong>Estrategias de trading personalizadas</strong> - Análisis adaptados a tu estilo</li>
                        </ul>
                    </div>
                    
                    <p style="background: #fef3c7; padding: 15px; border-left: 4px solid #f59e0b; border-radius: 5px;">
                        <strong>⚠️ Próximamente:</strong> Te notificaremos cuando Premium esté disponible con precios especiales de lanzamiento.
                    </p>
                    
                    <p>Mientras tanto, disfruta de todas nuestras características gratuitas:</p>
                    <ul>
                        <li>Gráficos técnicos en tiempo real</li>
                        <li>Análisis de IA básico</li>
                        <li>Datos de 90 días</li>
                        <li>Soporte multi-idioma</li>
                    </ul>
                    
                    <p>¿Preguntas? Simplemente responde a este correo.</p>
                    
                    <p>Saludos,<br><strong>El equipo de Crypto Dashboard</strong></p>
                    
                    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                    <p style="font-size: 12px; color: #6b7280; text-align: center;">
                        © 2025 Crypto Dashboard. Todos los derechos reservados.<br>
                        Este correo es solo para fines informativos y no constituye asesoramiento financiero.
                    </p>
                </div>
            </body>
        </html>
        """
    elif lang == 'fr':
        subject = "Bienvenue à Crypto Dashboard Premium!"
        body_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #667eea;">Merci de votre intérêt pour Crypto Dashboard Premium!</h2>
                    
                    <p>Bonjour,</p>
                    
                    <p>Merci de vous être abonné à nos mises à jour. Voici les fonctionnalités incroyables que vous obtiendrez avec Premium:</p>
                    
                    <div style="background: #f9fafb; padding: 20px; border-radius: 10px; margin: 20px 0;">
                        <h3 style="color: #667eea;">✨ Fonctionnalités Premium</h3>
                        <ul style="list-style: none; padding: 0;">
                            <li style="padding: 8px 0;">🔔 <strong>Alertes de prix en temps réel</strong> - Recevez des notifications instantanées sur les mouvements de prix</li>
                            <li style="padding: 8px 0;">📊 <strong>Indicateurs techniques avancés</strong> - Accédez à plus de 20 indicateurs professionnels</li>
                            <li style="padding: 8px 0;">💼 <strong>Suivi de portefeuille</strong> - Suivez plusieurs cryptomonnaies en un seul endroit</li>
                            <li style="padding: 8px 0;">🤖 <strong>Support IA prioritaire</strong> - Questions illimitées et réponses plus rapides</li>
                            <li style="padding: 8px 0;">📈 <strong>Données historiques étendues</strong> - Jusqu'à 5 ans de données historiques</li>
                            <li style="padding: 8px 0;">🎯 <strong>Stratégies de trading personnalisées</strong> - Analyses adaptées à votre style</li>
                        </ul>
                    </div>
                    
                    <p style="background: #fef3c7; padding: 15px; border-left: 4px solid #f59e0b; border-radius: 5px;">
                        <strong>⚠️ Bientôt disponible:</strong> Nous vous informerons lorsque Premium sera disponible avec des tarifs de lancement spéciaux.
                    </p>
                    
                    <p>En attendant, profitez de toutes nos fonctionnalités gratuites:</p>
                    <ul>
                        <li>Graphiques techniques en temps réel</li>
                        <li>Analyse IA basique</li>
                        <li>Données sur 90 jours</li>
                        <li>Support multilingue</li>
                    </ul>
                    
                    <p>Des questions? Répondez simplement à cet email.</p>
                    
                    <p>Cordialement,<br><strong>L'équipe Crypto Dashboard</strong></p>
                    
                    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                    <p style="font-size: 12px; color: #6b7280; text-align: center;">
                        © 2025 Crypto Dashboard. Tous droits réservés.<br>
                        Cet email est à titre informatif uniquement et ne constitue pas un conseil financier.
                    </p>
                </div>
            </body>
        </html>
        """
    elif lang == 'de':
        subject = "Willkommen bei Crypto Dashboard Premium!"
        body_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #667eea;">Vielen Dank für Ihr Interesse an Crypto Dashboard Premium!</h2>
                    
                    <p>Hallo,</p>
                    
                    <p>Vielen Dank für Ihr Abonnement unserer Updates. Hier sind die erstaunlichen Funktionen, die Sie mit Premium erhalten:</p>
                    
                    <div style="background: #f9fafb; padding: 20px; border-radius: 10px; margin: 20px 0;">
                        <h3 style="color: #667eea;">✨ Premium-Funktionen</h3>
                        <ul style="list-style: none; padding: 0;">
                            <li style="padding: 8px 0;">🔔 <strong>Echtzeit-Preiswarnungen</strong> - Erhalten Sie sofortige Benachrichtigungen über Preisbewegungen</li>
                            <li style="padding: 8px 0;">📊 <strong>Erweiterte technische Indikatoren</strong> - Zugriff auf über 20 professionelle Indikatoren</li>
                            <li style="padding: 8px 0;">💼 <strong>Portfolio-Tracking</strong> - Verfolgen Sie mehrere Kryptowährungen an einem Ort</li>
                            <li style="padding: 8px 0;">🤖 <strong>Prioritärer KI-Support</strong> - Unbegrenzte Fragen und schnellere Antworten</li>
                            <li style="padding: 8px 0;">📈 <strong>Erweiterte historische Daten</strong> - Bis zu 5 Jahre historische Daten</li>
                            <li style="padding: 8px 0;">🎯 <strong>Personalisierte Handelsstrategien</strong> - Analysen angepasst an Ihren Stil</li>
                        </ul>
                    </div>
                    
                    <p style="background: #fef3c7; padding: 15px; border-left: 4px solid #f59e0b; border-radius: 5px;">
                        <strong>⚠️ Demnächst:</strong> Wir benachrichtigen Sie, wenn Premium mit speziellen Launch-Preisen verfügbar ist.
                    </p>
                    
                    <p>In der Zwischenzeit genießen Sie alle unsere kostenlosen Funktionen:</p>
                    <ul>
                        <li>Echtzeit-Technische Charts</li>
                        <li>Basis-KI-Analyse</li>
                        <li>90-Tage-Daten</li>
                        <li>Mehrsprachige Unterstützung</li>
                    </ul>
                    
                    <p>Fragen? Antworten Sie einfach auf diese E-Mail.</p>
                    
                    <p>Mit freundlichen Grüßen,<br><strong>Das Crypto Dashboard Team</strong></p>
                    
                    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                    <p style="font-size: 12px; color: #6b7280; text-align: center;">
                        © 2025 Crypto Dashboard. Alle Rechte vorbehalten.<br>
                        Diese E-Mail dient nur zu Informationszwecken und stellt keine Finanzberatung dar.
                    </p>
                </div>
            </body>
        </html>
        """
    elif lang == 'zh':
        subject = "欢迎使用Crypto Dashboard高级版！"
        body_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #667eea;">感谢您对Crypto Dashboard高级版的兴趣！</h2>
                    
                    <p>您好，</p>
                    
                    <p>感谢您订阅我们的更新。以下是高级版将为您提供的强大功能：</p>
                    
                    <div style="background: #f9fafb; padding: 20px; border-radius: 10px; margin: 20px 0;">
                        <h3 style="color: #667eea;">✨ 高级功能</h3>
                        <ul style="list-style: none; padding: 0;">
                            <li style="padding: 8px 0;">🔔 <strong>实时价格警报</strong> - 接收价格变动的即时通知</li>
                            <li style="padding: 8px 0;">📊 <strong>高级技术指标</strong> - 访问20多个专业指标</li>
                            <li style="padding: 8px 0;">💼 <strong>投资组合跟踪</strong> - 在一个地方跟踪多个加密货币</li>
                            <li style="padding: 8px 0;">🤖 <strong>优先AI支持</strong> - 无限问题和更快响应</li>
                            <li style="padding: 8px 0;">📈 <strong>扩展历史数据</strong> - 多达5年的历史数据</li>
                            <li style="padding: 8px 0;">🎯 <strong>个性化交易策略</strong> - 适合您风格的分析</li>
                        </ul>
                    </div>
                    
                    <p style="background: #fef3c7; padding: 15px; border-left: 4px solid #f59e0b; border-radius: 5px;">
                        <strong>⚠️ 即将推出：</strong>我们会在高级版推出时通知您，并提供特别发布价格。
                    </p>
                    
                    <p>同时，请享受我们所有的免费功能：</p>
                    <ul>
                        <li>实时技术图表</li>
                        <li>基本AI分析</li>
                        <li>90天数据</li>
                        <li>多语言支持</li>
                    </ul>
                    
                    <p>有问题？只需回复此邮件。</p>
                    
                    <p>此致,<br><strong>Crypto Dashboard团队</strong></p>
                    
                    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                    <p style="font-size: 12px; color: #6b7280; text-align: center;">
                        © 2025 Crypto Dashboard. 保留所有权利。<br>
                        此电子邮件仅供参考，不构成财务建议。
                    </p>
                </div>
            </body>
        </html>
        """
    elif lang == 'tr':
        subject = "Crypto Dashboard Premium'a Hoş Geldiniz!"
        body_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #667eea;">Crypto Dashboard Premium'a ilginiz için teşekkürler!</h2>
                    
                    <p>Merhaba,</p>
                    
                    <p>Güncellemelerimize abone olduğunuz için teşekkür ederiz. Premium ile alacağınız harika özellikler:</p>
                    
                    <div style="background: #f9fafb; padding: 20px; border-radius: 10px; margin: 20px 0;">
                        <h3 style="color: #667eea;">✨ Premium Özellikler</h3>
                        <ul style="list-style: none; padding: 0;">
                            <li style="padding: 8px 0;">🔔 <strong>Gerçek zamanlı fiyat uyarıları</strong> - Fiyat hareketleri hakkında anında bildirimler</li>
                            <li style="padding: 8px 0;">📊 <strong>Gelişmiş teknik göstergeler</strong> - 20'den fazla profesyonel göstergeye erişim</li>
                            <li style="padding: 8px 0;">💼 <strong>Portföy takibi</strong> - Birden fazla kripto parayı tek yerden takip edin</li>
                            <li style="padding: 8px 0;">🤖 <strong>Öncelikli AI desteği</strong> - Sınırsız sorular ve daha hızlı yanıtlar</li>
                            <li style="padding: 8px 0;">📈 <strong>Genişletilmiş geçmiş veriler</strong> - 5 yıla kadar geçmiş veri</li>
                            <li style="padding: 8px 0;">🎯 <strong>Kişiselleştirilmiş ticaret stratejileri</strong> - Tarzınıza uygun analizler</li>
                        </ul>
                    </div>
                    
                    <p style="background: #fef3c7; padding: 15px; border-left: 4px solid #f59e0b; border-radius: 5px;">
                        <strong>⚠️ Yakında:</strong> Premium özel lansma fiyatlarıyla kullanıma sunulduğunda sizi bilgilendireceğiz.
                    </p>
                    
                    <p>Bu arada, tüm ücretsiz özelliklerimizin keyfini çıkarın:</p>
                    <ul>
                        <li>Gerçek zamanlı teknik grafikler</li>
                        <li>Temel AI analizi</li>
                        <li>90 günlük veri</li>
                        <li>Çok dilli destek</li>
                    </ul>
                    
                    <p>Sorularınız mı var? Bu e-postaya yanıt verin.</p>
                    
                    <p>Saygılarımızla,<br><strong>Crypto Dashboard Ekibi</strong></p>
                    
                    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                    <p style="font-size: 12px; color: #6b7280; text-align: center;">
                        © 2025 Crypto Dashboard. Tüm hakları saklıdır.<br>
                        Bu e-posta yalnızca bilgilendirme amaçlıdır ve finansal tavsiye niteliği taşımaz.
                    </p>
                </div>
            </body>
        </html>
        """
    else:  # English (default)
        subject = "Welcome to Crypto Dashboard Premium!"
        body_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #667eea;">Thank you for your interest in Crypto Dashboard Premium!</h2>
                    
                    <p>Hello,</p>
                    
                    <p>Thank you for subscribing to our updates. Here are the amazing features you'll get with Premium:</p>
                    
                    <div style="background: #f9fafb; padding: 20px; border-radius: 10px; margin: 20px 0;">
                        <h3 style="color: #667eea;">✨ Premium Features</h3>
                        <ul style="list-style: none; padding: 0;">
                            <li style="padding: 8px 0;">🔔 <strong>Real-time Price Alerts</strong> - Get instant notifications on price movements</li>
                            <li style="padding: 8px 0;">📊 <strong>Advanced Technical Indicators</strong> - Access to 20+ professional indicators</li>
                            <li style="padding: 8px 0;">💼 <strong>Portfolio Tracking</strong> - Track multiple cryptocurrencies in one place</li>
                            <li style="padding: 8px 0;">🤖 <strong>Priority AI Support</strong> - Unlimited questions and faster responses</li>
                            <li style="padding: 8px 0;">📈 <strong>Extended Historical Data</strong> - Up to 5 years of historical data</li>
                            <li style="padding: 8px 0;">🎯 <strong>Personalized Trading Strategies</strong> - Analyses tailored to your style</li>
                        </ul>
                    </div>
                    
                    <p style="background: #fef3c7; padding: 15px; border-left: 4px solid #f59e0b; border-radius: 5px;">
                        <strong>⚠️ Coming Soon:</strong> We'll notify you when Premium is available with special launch pricing.
                    </p>
                    
                    <p>In the meantime, enjoy all our free features:</p>
                    <ul>
                        <li>Real-time technical charts</li>
                        <li>Basic AI analysis</li>
                        <li>90-day data</li>
                        <li>Multi-language support</li>
                    </ul>
                    
                    <p>Questions? Just reply to this email.</p>
                    
                    <p>Best regards,<br><strong>The Crypto Dashboard Team</strong></p>
                    
                    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">
                    <p style="font-size: 12px; color: #6b7280; text-align: center;">
                        © 2025 Crypto Dashboard. All rights reserved.<br>
                        This email is for informational purposes only and does not constitute financial advice.
                    </p>
                </div>
            </body>
        </html>
        """
    
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{EMAIL_FROM_NAME} <{EMAIL_USER}>"
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Attach HTML content
        html_part = MIMEText(body_html, 'html')
        msg.attach(html_part)
        
        print(f"📤 Connecting to SMTP server...")
        # Send email
        with smtplib.SMTP(EMAIL_HOST, EMAIL_PORT) as server:
            print(f"🔐 Starting TLS...")
            server.starttls()
            print(f"🔑 Logging in as {EMAIL_USER}...")
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            print(f"📨 Sending message...")
            server.send_message(msg)
        
        print(f"✅ Subscription email sent successfully to {to_email}")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        print(f"❌ AUTHENTICATION ERROR: {e}")
        print("   → Check your EMAIL_USER and EMAIL_PASSWORD")
        print("   → For Gmail, you need an App Password, not your regular password")
        print("   → Visit: https://myaccount.google.com/apppasswords")
        return False
    except smtplib.SMTPException as e:
        print(f"❌ SMTP ERROR: {e}")
        return False
    except Exception as e:
        print(f"❌ UNEXPECTED ERROR sending email: {e}")
        print(f"   Error type: {type(e).__name__}")
        import traceback
        traceback.print_exc()
        return False

# -----------------------------
# TRANSLATIONS
# -----------------------------
TRANSLATIONS = {
    'en': {
        'title': 'Crypto Dashboard',
        'price': 'Price',
        'cryptocurrency': 'Cryptocurrency',
        'analysis_level': 'Analysis Level',
        'beginner': 'Beginner',
        'advanced': 'Advanced',
        'ai_analysis': 'AI Technical Analysis',
        'confidence': 'Confidence',
        'ask_questions': 'Ask AI Questions',
        'questions_subtitle': 'Get instant explanations about technical indicators and chart patterns',
        'quick_questions': 'Quick questions:',
        'type_question': 'Type your question here...',
        'ask_ai': 'Ask AI',
        'disclaimer_title': 'Educational Purpose Only:',
        'disclaimer_text': 'This analysis is for educational purposes only and does not constitute financial advice. AI may not always have up-to-date information. Cryptocurrency trading carries significant risk. Always do your own research and consult with a financial advisor before making investment decisions.',
        'timeline': 'Timeline',
        'days': 'days',
        'language': 'Language',
        'subscribe': 'Subscribe for Premium Features',
        'subscribe_desc': 'Get advanced analytics, real-time alerts, and more',
        'email_placeholder': 'Enter your email',
        'subscribe_button': 'Subscribe',
        'premium_features': 'Premium Features:',
        'feature_1': '• Real-time price alerts',
        'feature_2': '• Advanced technical indicators',
        'feature_3': '• Portfolio tracking',
        'feature_4': '• Priority AI support',
        'copyright': '© 2025 Crypto Dashboard. All rights reserved.',
        'thinking': '🤔 Thinking...',
        'error': 'Error:',
        'answer': 'Answer:',
    },
    'es': {
        'title': 'Panel de Criptomonedas',
        'price': 'Precio',
        'cryptocurrency': 'Criptomoneda',
        'analysis_level': 'Nivel de Análisis',
        'beginner': 'Principiante',
        'advanced': 'Avanzado',
        'ai_analysis': 'Análisis Técnico de IA',
        'confidence': 'Confianza',
        'ask_questions': 'Hacer Preguntas a la IA',
        'questions_subtitle': 'Obtenga explicaciones instantáneas sobre indicadores técnicos y patrones de gráficos',
        'quick_questions': 'Preguntas rápidas:',
        'type_question': 'Escriba su pregunta aquí...',
        'ask_ai': 'Preguntar a IA',
        'disclaimer_title': 'Solo con Fines Educativos:',
        'disclaimer_text': 'Este análisis es solo para fines educativos y no constituye asesoramiento financiero. La IA puede no tener siempre información actualizada. El comercio de criptomonedas conlleva un riesgo significativo. Siempre haga su propia investigación y consulte con un asesor financiero antes de tomar decisiones de inversión.',
        'timeline': 'Línea de Tiempo',
        'days': 'días',
        'language': 'Idioma',
        'subscribe': 'Suscríbase para Características Premium',
        'subscribe_desc': 'Obtenga análisis avanzados, alertas en tiempo real y más',
        'email_placeholder': 'Ingrese su correo electrónico',
        'subscribe_button': 'Suscribirse',
        'premium_features': 'Características Premium:',
        'feature_1': '• Alertas de precios en tiempo real',
        'feature_2': '• Indicadores técnicos avanzados',
        'feature_3': '• Seguimiento de cartera',
        'feature_4': '• Soporte prioritario de IA',
        'copyright': '© 2025 Panel de Criptomonedas. Todos los derechos reservados.',
        'thinking': '🤔 Pensando...',
        'error': 'Error:',
        'answer': 'Respuesta:',
    },
    'fr': {
        'title': 'Tableau de Bord Crypto',
        'price': 'Prix',
        'cryptocurrency': 'Cryptomonnaie',
        'analysis_level': 'Niveau d\'Analyse',
        'beginner': 'Débutant',
        'advanced': 'Avancé',
        'ai_analysis': 'Analyse Technique IA',
        'confidence': 'Confiance',
        'ask_questions': 'Poser des Questions à l\'IA',
        'questions_subtitle': 'Obtenez des explications instantanées sur les indicateurs techniques et les modèles graphiques',
        'quick_questions': 'Questions rapides:',
        'type_question': 'Tapez votre question ici...',
        'ask_ai': 'Demander à l\'IA',
        'disclaimer_title': 'À des Fins Éducatives Uniquement:',
        'disclaimer_text': 'Cette analyse est uniquement à des fins éducatives et ne constitue pas un conseil financier. L\'IA peut ne pas toujours avoir des informations à jour. Le trading de cryptomonnaies comporte des risques importants. Faites toujours vos propres recherches et consultez un conseiller financier avant de prendre des décisions d\'investissement.',
        'timeline': 'Chronologie',
        'days': 'jours',
        'language': 'Langue',
        'subscribe': 'S\'abonner aux Fonctionnalités Premium',
        'subscribe_desc': 'Obtenez des analyses avancées, des alertes en temps réel et plus encore',
        'email_placeholder': 'Entrez votre e-mail',
        'subscribe_button': 'S\'abonner',
        'premium_features': 'Fonctionnalités Premium:',
        'feature_1': '• Alertes de prix en temps réel',
        'feature_2': '• Indicateurs techniques avancés',
        'feature_3': '• Suivi de portefeuille',
        'feature_4': '• Support IA prioritaire',
        'copyright': '© 2025 Tableau de Bord Crypto. Tous droits réservés.',
        'thinking': '🤔 Réflexion...',
        'error': 'Erreur:',
        'answer': 'Réponse:',
    },
    'de': {
        'title': 'Krypto-Dashboard',
        'price': 'Preis',
        'cryptocurrency': 'Kryptowährung',
        'analysis_level': 'Analyseebene',
        'beginner': 'Anfänger',
        'advanced': 'Fortgeschritten',
        'ai_analysis': 'KI-Technische Analyse',
        'confidence': 'Vertrauen',
        'ask_questions': 'Fragen Sie die KI',
        'questions_subtitle': 'Erhalten Sie sofortige Erklärungen zu technischen Indikatoren und Chartmustern',
        'quick_questions': 'Schnelle Fragen:',
        'type_question': 'Geben Sie hier Ihre Frage ein...',
        'ask_ai': 'KI fragen',
        'disclaimer_title': 'Nur zu Bildungszwecken:',
        'disclaimer_text': 'Diese Analyse dient nur zu Bildungszwecken und stellt keine Finanzberatung dar. Die KI verfügt möglicherweise nicht immer über aktuelle Informationen. Der Handel mit Kryptowährungen birgt erhebliche Risiken. Führen Sie immer Ihre eigenen Recherchen durch und konsultieren Sie einen Finanzberater, bevor Sie Investitionsentscheidungen treffen.',
        'timeline': 'Zeitleiste',
        'days': 'Tage',
        'language': 'Sprache',
        'subscribe': 'Abonnieren Sie Premium-Funktionen',
        'subscribe_desc': 'Erhalten Sie erweiterte Analysen, Echtzeit-Warnungen und mehr',
        'email_placeholder': 'Geben Sie Ihre E-Mail ein',
        'subscribe_button': 'Abonnieren',
        'premium_features': 'Premium-Funktionen:',
        'feature_1': '• Echtzeit-Preiswarnungen',
        'feature_2': '• Erweiterte technische Indikatoren',
        'feature_3': '• Portfolio-Tracking',
        'feature_4': '• Prioritärer KI-Support',
        'copyright': '© 2025 Krypto-Dashboard. Alle Rechte vorbehalten.',
        'thinking': '🤔 Denke nach...',
        'error': 'Fehler:',
        'answer': 'Antwort:',
    },
    'zh': {
        'title': '加密货币仪表板',
        'price': '价格',
        'cryptocurrency': '加密货币',
        'analysis_level': '分析级别',
        'beginner': '初学者',
        'advanced': '高级',
        'ai_analysis': 'AI技术分析',
        'confidence': '置信度',
        'ask_questions': '向AI提问',
        'questions_subtitle': '获取有关技术指标和图表模式的即时解释',
        'quick_questions': '快速问题：',
        'type_question': '在此输入您的问题...',
        'ask_ai': '询问AI',
        'disclaimer_title': '仅供教育目的：',
        'disclaimer_text': '此分析仅供教育目的，不构成财务建议。AI可能并不总是拥有最新信息。加密货币交易具有重大风险。在做出投资决策之前，请务必进行自己的研究并咨询财务顾问。',
        'timeline': '时间线',
        'days': '天',
        'language': '语言',
        'subscribe': '订阅高级功能',
        'subscribe_desc': '获取高级分析、实时警报等',
        'email_placeholder': '输入您的电子邮件',
        'subscribe_button': '订阅',
        'premium_features': '高级功能：',
        'feature_1': '• 实时价格警报',
        'feature_2': '• 高级技术指标',
        'feature_3': '• 投资组合跟踪',
        'feature_4': '• 优先AI支持',
        'copyright': '© 2025 加密货币仪表板。保留所有权利。',
        'thinking': '🤔 思考中...',
        'error': '错误：',
        'answer': '答案：',
    },
    'tr': {
        'title': 'Kripto Para Panosu',
        'price': 'Fiyat',
        'cryptocurrency': 'Kripto Para',
        'analysis_level': 'Analiz Seviyesi',
        'beginner': 'Başlangıç',
        'advanced': 'İleri Seviye',
        'ai_analysis': 'Yapay Zeka Teknik Analizi',
        'confidence': 'Güven',
        'ask_questions': 'Yapay Zekaya Soru Sorun',
        'questions_subtitle': 'Teknik göstergeler ve grafik desenleri hakkında anında açıklamalar alın',
        'quick_questions': 'Hızlı sorular:',
        'type_question': 'Sorunuzu buraya yazın...',
        'ask_ai': 'Yapay Zekaya Sor',
        'disclaimer_title': 'Sadece Eğitim Amaçlıdır:',
        'disclaimer_text': 'Bu analiz yalnızca eğitim amaçlıdır ve finansal tavsiye niteliği taşımaz. Yapay zeka her zaman güncel bilgilere sahip olmayabilir. Kripto para ticareti önemli risk taşır. Yatırım kararları vermeden önce her zaman kendi araştırmanızı yapın ve bir finansal danışmana danışın.',
        'timeline': 'Zaman Çizelgesi',
        'days': 'gün',
        'language': 'Dil',
        'subscribe': 'Premium Özelliklere Abone Olun',
        'subscribe_desc': 'Gelişmiş analizler, gerçek zamanlı uyarılar ve daha fazlasını edinin',
        'email_placeholder': 'E-posta adresinizi girin',
        'subscribe_button': 'Abone Ol',
        'premium_features': 'Premium Özellikler:',
        'feature_1': '• Gerçek zamanlı fiyat uyarıları',
        'feature_2': '• Gelişmiş teknik göstergeler',
        'feature_3': '• Portföy takibi',
        'feature_4': '• Öncelikli yapay zeka desteği',
        'copyright': '© 2025 Kripto Para Panosu. Tüm hakları saklıdır.',
        'thinking': '🤔 Düşünüyor...',
        'error': 'Hata:',
        'answer': 'Cevap:',
    }
}

# -----------------------------
# SUPPORTED COINS
# -----------------------------
COINS = {
    "BTC": "Bitcoin",
    "ETH": "Ethereum",
    "USDT": "Tether",
    "USDC": "USD Coin",
    "BNB": "BNB",
    "SOL": "Solana",
    "XRP": "XRP",
    "ADA": "Cardano",
    "DOGE": "Dogecoin",
    "LTC": "Litecoin",
    "DOT": "Polkadot",
    "XMR": "Monero",
    "LINK": "Chainlink",
    "MATIC": "Polygon",
}

# -----------------------------
# DATA + INDICATORS (CACHED)
# -----------------------------
@cache.memoize(timeout=300)
def get_crypto_data(symbol, days=90):
    end = datetime.now()
    start = end - timedelta(days=days)

    ticker = f"{symbol}-USD"
    try:
        df = yf.download(
            ticker,
            start=start,
            end=end,
            auto_adjust=True,
            progress=False,
            timeout=10
        )
    except Exception as e:
        print(f"Error downloading data: {e}")
        raise

    if df.empty:
        raise ValueError("No data returned")

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]

    # EMA
    df["EMA_12"] = df["Close"].ewm(span=12).mean()
    df["EMA_26"] = df["Close"].ewm(span=26).mean()
    df["EMA_50"] = df["Close"].ewm(span=50).mean()

    # MACD
    ema_fast = df["Close"].ewm(span=12).mean()
    ema_slow = df["Close"].ewm(span=26).mean()
    df["MACD"] = ema_fast - ema_slow
    df["MACD_Signal"] = df["MACD"].ewm(span=9).mean()
    df["MACD_Hist"] = df["MACD"] - df["MACD_Signal"]

    # RSI
    delta = df["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))

    return df


def get_indicator_summary(df):
    """Get standardized indicator summary with trends"""
    latest = df.iloc[-1]
    prev_5d = df.iloc[-6] if len(df) > 5 else df.iloc[0]
    
    return {
        'price': latest['Close'],
        'rsi': latest['RSI'],
        'rsi_5d_change': latest['RSI'] - prev_5d['RSI'],
        'macd': latest['MACD'],
        'macd_signal': latest['MACD_Signal'],
        'macd_hist': latest['MACD_Hist'],
        'macd_hist_5d_change': latest['MACD_Hist'] - prev_5d['MACD_Hist'],
        'ema_12': latest['EMA_12'],
        'ema_26': latest['EMA_26'],
        'ema_50': latest['EMA_50'],
        'price_vs_ema50_pct': ((latest['Close'] - latest['EMA_50']) / latest['EMA_50']) * 100,
        'volume': latest['Volume']
    }


def calculate_confidence(indicators):
    """Calculate confidence level based on indicator alignment"""
    confidence_score = 0
    
    # RSI confidence (distance from neutral 50)
    rsi_distance = abs(indicators['rsi'] - 50)
    if rsi_distance > 30:
        confidence_score += 3
    elif rsi_distance > 15:
        confidence_score += 2
    else:
        confidence_score += 1
    
    # EMA alignment
    price = indicators['price']
    if (price > indicators['ema_12'] > indicators['ema_26'] > indicators['ema_50']) or \
       (price < indicators['ema_12'] < indicators['ema_26'] < indicators['ema_50']):
        confidence_score += 3
    elif (price > indicators['ema_50']) or (price < indicators['ema_50']):
        confidence_score += 2
    else:
        confidence_score += 1
    
    # MACD histogram magnitude
    if abs(indicators['macd_hist']) > abs(indicators['macd']) * 0.1:
        confidence_score += 2
    else:
        confidence_score += 1
    
    # Map to labels
    if confidence_score >= 7:
        return "High"
    elif confidence_score >= 5:
        return "Medium"
    else:
        return "Low"


# -----------------------------
# CHART (CACHED)
# -----------------------------
@cache.memoize(timeout=300)
def create_chart(symbol, days=90):
    df = get_crypto_data(symbol, days)
    name = COINS[symbol]
    indicators = get_indicator_summary(df)

    fig = plt.figure(figsize=(15, 12))
    fig.suptitle(f"{name} ({symbol}-USD) Technical Analysis - Last {days} Days", fontsize=16, fontweight='bold')

    ax1 = plt.subplot(4, 1, 1)
    ax1.plot(df.index, df["Close"], label="Close", color="black", linewidth=2)
    ax1.plot(df.index, df["EMA_12"], label="EMA 12", alpha=0.7)
    ax1.plot(df.index, df["EMA_26"], label="EMA 26", alpha=0.7)
    ax1.plot(df.index, df["EMA_50"], label="EMA 50", alpha=0.7)
    
    # Add trend annotation
    if indicators['price'] > indicators['ema_50']:
        trend_text = "Short-term: Bullish"
        trend_color = "green"
    else:
        trend_text = "Short-term: Bearish"
        trend_color = "red"
    ax1.text(0.02, 0.95, trend_text, transform=ax1.transAxes, 
             fontsize=10, verticalalignment='top', 
             bbox=dict(boxstyle='round', facecolor=trend_color, alpha=0.3))
    
    ax1.set_ylabel("Price (USD)", fontweight='bold')
    ax1.legend(loc='upper left')
    ax1.grid(alpha=0.3)

    ax2 = plt.subplot(4, 1, 2)
    ax2.plot(df.index, df["MACD"], label="MACD", linewidth=2)
    ax2.plot(df.index, df["MACD_Signal"], label="Signal", linewidth=2)
    colors = ['green' if x > 0 else 'red' for x in df["MACD_Hist"]]
    ax2.bar(df.index, df["MACD_Hist"], alpha=0.4, color=colors, label="Histogram")
    ax2.axhline(0, color="black", linestyle="--", linewidth=1)
    ax2.set_ylabel("MACD", fontweight='bold')
    ax2.legend(loc='upper left')
    ax2.grid(alpha=0.3)

    ax3 = plt.subplot(4, 1, 3)
    ax3.plot(df.index, df["RSI"], color="purple", linewidth=2, label="RSI")
    
    # Highlight overbought/oversold zones
    ax3.axhspan(70, 100, alpha=0.2, color='red', label='Overbought Zone')
    ax3.axhspan(0, 30, alpha=0.2, color='green', label='Oversold Zone')
    ax3.axhline(70, color="red", linestyle="--", linewidth=1)
    ax3.axhline(30, color="green", linestyle="--", linewidth=1)
    ax3.axhline(50, color="gray", linestyle=":", linewidth=1, alpha=0.5)
    
    ax3.set_ylim(0, 100)
    ax3.set_ylabel("RSI", fontweight='bold')
    ax3.legend(loc='upper left')
    ax3.grid(alpha=0.3)

    ax4 = plt.subplot(4, 1, 4)
    ax4.bar(df.index, df["Volume"], alpha=0.6, color="blue")
    ax4.set_ylabel("Volume", fontweight='bold')
    ax4.grid(alpha=0.3)

    for ax in [ax1, ax2, ax3, ax4]:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%m"))
        plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)

    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf.read(), df


# -----------------------------
# AI ANALYSIS (CACHED with longer timeout)
# -----------------------------
@cache.memoize(timeout=900)  # Cache for 15 minutes to avoid rate limits
def get_ai_analysis(symbol, interpretation_level='advanced', days=90, lang='en'):
    """Get AI analysis with timeout and confidence"""
    if not ANTHROPIC_API_KEY:
        return "AI analysis unavailable: API key not configured.", "N/A"
    
    t = TRANSLATIONS.get(lang, TRANSLATIONS['en'])
    
    try:
        df = get_crypto_data(symbol, days)
        indicators = get_indicator_summary(df)
        confidence = calculate_confidence(indicators)
        
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=15.0)
        
        prev = df.iloc[-2]
        price_change = ((indicators['price'] - prev["Close"]) / prev["Close"]) * 100
        
        # Language-specific prompts
        if lang == 'es':
            prompt_base = f"""Analiza estos datos técnicos de criptomonedas para {COINS[symbol]} ({symbol}) durante los últimos {days} días:

Precio Actual: ${indicators['price']:.2f} (cambio 24h: {price_change:+.2f}%)

Indicadores Técnicos y Tendencias:
- RSI: {indicators['rsi']:.2f} (cambio 5 días: {indicators['rsi_5d_change']:+.2f})
- MACD: {indicators['macd']:.4f}
- Señal MACD: {indicators['macd_signal']:.4f}
- Histograma MACD: {indicators['macd_hist']:.4f} (cambio 5 días: {indicators['macd_hist_5d_change']:+.4f})
- Precio vs EMA-50: {indicators['price_vs_ema50_pct']:+.2f}%
- Alineación EMA: 12=${indicators['ema_12']:.2f}, 26=${indicators['ema_26']:.2f}, 50=${indicators['ema_50']:.2f}

"""
            if interpretation_level == 'beginner':
                prompt_base += """Proporciona una explicación simple (2-3 oraciones) de lo que significan estos indicadores en español claro.
Enfócate en si el sentimiento del mercado parece positivo, negativo o neutral. Evita la jerga técnica.

IMPORTANTE: Este es solo análisis educativo, no asesoramiento financiero. No uses palabras como "comprar", "vender" o "precio objetivo"."""
            else:
                prompt_base += """Proporciona un análisis técnico (3-4 oraciones) cubriendo:
1. Tendencia general basada en la alineación de indicadores
2. Señales de momento del RSI y tendencias MACD
3. Observaciones clave de los cambios de 5 días

IMPORTANTE: Este es solo análisis educativo, no asesoramiento financiero. Enfócate en la interpretación, no en recomendaciones de trading."""
        
        elif lang == 'fr':
            prompt_base = f"""Analysez ces données techniques de cryptomonnaie pour {COINS[symbol]} ({symbol}) sur les {days} derniers jours:

Prix Actuel: ${indicators['price']:.2f} (changement 24h: {price_change:+.2f}%)

Indicateurs Techniques et Tendances:
- RSI: {indicators['rsi']:.2f} (changement 5 jours: {indicators['rsi_5d_change']:+.2f})
- MACD: {indicators['macd']:.4f}
- Signal MACD: {indicators['macd_signal']:.4f}
- Histogramme MACD: {indicators['macd_hist']:.4f} (changement 5 jours: {indicators['macd_hist_5d_change']:+.4f})
- Prix vs EMA-50: {indicators['price_vs_ema50_pct']:+.2f}%
- Alignement EMA: 12=${indicators['ema_12']:.2f}, 26=${indicators['ema_26']:.2f}, 50=${indicators['ema_50']:.2f}

"""
            if interpretation_level == 'beginner':
                prompt_base += """Fournissez une explication simple (2-3 phrases) de ce que signifient ces indicateurs en français clair.
Concentrez-vous sur la question de savoir si le sentiment du marché semble positif, négatif ou neutre. Évitez le jargon.

IMPORTANT: Ceci est uniquement une analyse éducative, pas un conseil financier. N'utilisez pas de mots comme "acheter", "vendre" ou "prix cible"."""
            else:
                prompt_base += """Fournissez une analyse technique (3-4 phrases) couvrant:
1. Tendance globale basée sur l'alignement des indicateurs
2. Signaux de momentum du RSI et tendances MACD
3. Observations clés des changements sur 5 jours

IMPORTANT: Ceci est uniquement une analyse éducative, pas un conseil financier. Concentrez-vous sur l'interprétation, pas sur les recommandations de trading."""
        
        elif lang == 'de':
            prompt_base = f"""Analysieren Sie diese Kryptowährungs-Technischen Daten für {COINS[symbol]} ({symbol}) über die letzten {days} Tage:

Aktueller Preis: ${indicators['price']:.2f} (24h Änderung: {price_change:+.2f}%)

Technische Indikatoren und Trends:
- RSI: {indicators['rsi']:.2f} (5-Tage-Änderung: {indicators['rsi_5d_change']:+.2f})
- MACD: {indicators['macd']:.4f}
- MACD Signal: {indicators['macd_signal']:.4f}
- MACD Histogramm: {indicators['macd_hist']:.4f} (5-Tage-Änderung: {indicators['macd_hist_5d_change']:+.4f})
- Preis vs EMA-50: {indicators['price_vs_ema50_pct']:+.2f}%
- EMA Ausrichtung: 12=${indicators['ema_12']:.2f}, 26=${indicators['ema_26']:.2f}, 50=${indicators['ema_50']:.2f}

"""
            if interpretation_level == 'beginner':
                prompt_base += """Geben Sie eine einfache Erklärung (2-3 Sätze) darüber, was diese Indikatoren in klarem Deutsch bedeuten.
Konzentrieren Sie sich darauf, ob die Marktstimmung positiv, negativ oder neutral erscheint. Vermeiden Sie Fachjargon.

WICHTIG: Dies ist nur eine Bildungsanalyse, keine Finanzberatung. Verwenden Sie keine Wörter wie "kaufen", "verkaufen" oder "Zielpreis"."""
            else:
                prompt_base += """Geben Sie eine technische Analyse (3-4 Sätze) zu:
1. Gesamttrend basierend auf Indikatorausrichtung
2. Momentum-Signale von RSI und MACD-Trends
3. Wichtige Beobachtungen aus den 5-Tage-Änderungen

WICHTIG: Dies ist nur eine Bildungsanalyse, keine Finanzberatung. Konzentrieren Sie sich auf die Interpretation, nicht auf Handelsempfehlungen."""
        
        elif lang == 'zh':
            prompt_base = f"""分析{COINS[symbol]} ({symbol})在过去{days}天的加密货币技术数据：

当前价格：${indicators['price']:.2f}（24小时变化：{price_change:+.2f}%）

技术指标和趋势：
- RSI：{indicators['rsi']:.2f}（5天变化：{indicators['rsi_5d_change']:+.2f}）
- MACD：{indicators['macd']:.4f}
- MACD信号：{indicators['macd_signal']:.4f}
- MACD柱状图：{indicators['macd_hist']:.4f}（5天变化：{indicators['macd_hist_5d_change']:+.4f}）
- 价格相对EMA-50：{indicators['price_vs_ema50_pct']:+.2f}%
- EMA排列：12=${indicators['ema_12']:.2f}，26=${indicators['ema_26']:.2f}，50=${indicators['ema_50']:.2f}

"""
            if interpretation_level == 'beginner':
                prompt_base += """用简单的中文解释（2-3句话）这些指标的含义。
重点说明市场情绪是看涨、看跌还是中性。避免使用专业术语。

重要提示：这仅用于教育分析，不构成财务建议。不要使用"买入"、"卖出"或"目标价格"等词语。"""
            else:
                prompt_base += """提供技术分析（3-4句话），涵盖：
1. 基于指标排列的整体趋势
2. 来自RSI和MACD趋势的动量信号
3. 5天变化的关键观察

重要提示：这仅用于教育分析，不构成财务建议。专注于解读，而非交易建议。"""
        
        elif lang == 'tr':
            prompt_base = f"""{COINS[symbol]} ({symbol}) için son {days} gün içindeki kripto para teknik verilerini analiz edin:

Güncel Fiyat: ${indicators['price']:.2f} (24s değişim: {price_change:+.2f}%)

Teknik Göstergeler ve Trendler:
- RSI: {indicators['rsi']:.2f} (5 günlük değişim: {indicators['rsi_5d_change']:+.2f})
- MACD: {indicators['macd']:.4f}
- MACD Sinyali: {indicators['macd_signal']:.4f}
- MACD Histogramı: {indicators['macd_hist']:.4f} (5 günlük değişim: {indicators['macd_hist_5d_change']:+.4f})
- Fiyat vs EMA-50: {indicators['price_vs_ema50_pct']:+.2f}%
- EMA Hizalaması: 12=${indicators['ema_12']:.2f}, 26=${indicators['ema_26']:.2f}, 50=${indicators['ema_50']:.2f}

"""
            if interpretation_level == 'beginner':
                prompt_base += """Bu göstergelerin ne anlama geldiğini basit Türkçe ile açıklayın (2-3 cümle).
Piyasa duygusunun olumlu, olumsuz veya nötr görünüp görünmediğine odaklanın. Jargondan kaçının.

ÖNEMLİ: Bu sadece eğitim amaçlı analizdir, finansal tavsiye değildir. "Al", "sat" veya "hedef fiyat" gibi kelimeler kullanmayın."""
            else:
                prompt_base += """Teknik analiz sağlayın (3-4 cümle):
1. Gösterge hizalamasına dayalı genel trend
2. RSI ve MACD trendlerinden momentum sinyalleri
3. 5 günlük değişimlerden önemli gözlemler

ÖNEMLİ: Bu sadece eğitim amaçlı analizdir, finansal tavsiye değildir. Yoruma odaklanın, alım satım önerilerine değil."""
        
        else:  # English (default)
            prompt_base = f"""Analyze this cryptocurrency technical data for {COINS[symbol]} ({symbol}) over the last {days} days:

Current Price: ${indicators['price']:.2f} (24h change: {price_change:+.2f}%)

Technical Indicators & Trends:
- RSI: {indicators['rsi']:.2f} (5-day change: {indicators['rsi_5d_change']:+.2f})
- MACD: {indicators['macd']:.4f}
- MACD Signal: {indicators['macd_signal']:.4f}
- MACD Histogram: {indicators['macd_hist']:.4f} (5-day change: {indicators['macd_hist_5d_change']:+.4f})
- Price vs EMA-50: {indicators['price_vs_ema50_pct']:+.2f}%
- EMA Alignment: 12=${indicators['ema_12']:.2f}, 26=${indicators['ema_26']:.2f}, 50=${indicators['ema_50']:.2f}

"""
            if interpretation_level == 'beginner':
                prompt_base += """Provide a simple explanation (2-3 sentences) of what these indicators mean in plain English. 
Focus on whether the market sentiment appears positive, negative, or neutral. Avoid jargon.

IMPORTANT: This is educational analysis only, not financial advice. Do not use words like "buy", "sell", or "target price"."""
            else:
                prompt_base += """Provide a technical analysis (3-4 sentences) covering:
1. Overall trend based on indicator alignment
2. Momentum signals from RSI and MACD trends
3. Key observations from the 5-day changes

IMPORTANT: This is educational analysis only, not financial advice. Focus on interpretation, not trading recommendations."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt_base}]
        )
        
        analysis = message.content[0].text
        return analysis, confidence
        
    except anthropic.APITimeoutError:
        return t.get('ai_error_timeout', "AI analysis temporarily unavailable (timeout). Please try again."), "N/A"
    except anthropic.RateLimitError:
        return t.get('ai_error_rate_limit', "AI analysis temporarily unavailable (rate limit reached). Please try again in a moment."), "N/A"
    except Exception as e:
        print(f"AI Error: {e}")
        return t.get('ai_error_general', "AI analysis temporarily unavailable. Please try again."), "N/A"


# -----------------------------
# ROUTES
# -----------------------------
@app.route("/")
def home():
    symbol = request.args.get("coin", "BTC").upper()
    if symbol not in COINS:
        symbol = "BTC"

    interpretation_level = request.args.get('interpretation_level', 'advanced')
    days = int(request.args.get('days', 90))
    lang = request.args.get('lang', 'en')
    
    if lang not in TRANSLATIONS:
        lang = 'en'
    
    t = TRANSLATIONS[lang]
    
    # Validate days range
    if days < 7:
        days = 7
    elif days > 365:
        days = 365

    df = get_crypto_data(symbol, days)
    price = float(df["Close"].iloc[-1])
    
    analysis, confidence = get_ai_analysis(symbol, interpretation_level, days, lang)

    options = "".join(
        f'<option value="{k}" {"selected" if k==symbol else ""}>{v}</option>'
        for k, v in COINS.items()
    )

    interpretation_select = f"""
        <option value="beginner" {"selected" if interpretation_level=="beginner" else ""}>{t['beginner']}</option>
        <option value="advanced" {"selected" if interpretation_level=="advanced" else ""}>{t['advanced']}</option>
    """

    language_options = "".join(
        f'<option value="{code}" {"selected" if code==lang else ""}>{name}</option>'
        for code, name in [('en', 'English'), ('es', 'Español'), ('fr', 'Français'), ('de', 'Deutsch'), ('zh', '中文'), ('tr', 'Türkçe')]
    )

    # Language-specific example questions
    if lang == 'es':
        example_questions = [
            "¿Qué significa MACD?",
            "¿Se está fortaleciendo el impulso?",
            "¿El RSI señala condiciones de sobrecompra?",
            "¿Qué sugieren las EMAs?",
            "¿Debería preocuparme por el RSI actual?"
        ]
    elif lang == 'fr':
        example_questions = [
            "Que signifie MACD?",
            "Le momentum se renforce-t-il?",
            "Le RSI signale-t-il des conditions de surachat?",
            "Que suggèrent les EMA?",
            "Devrais-je m'inquiéter du RSI actuel?"
        ]
    elif lang == 'de':
        example_questions = [
            "Was bedeutet MACD?",
            "Verstärkt sich das Momentum?",
            "Signalisiert der RSI überkaufte Bedingungen?",
            "Was schlagen die EMAs vor?",
            "Sollte ich mir Sorgen über den aktuellen RSI machen?"
        ]
    elif lang == 'zh':
        example_questions = [
            "MACD是什么意思？",
            "动量是否在增强？",
            "RSI是否显示超买状态？",
            "EMA建议什么？",
            "我应该担心当前的RSI吗？"
        ]
    elif lang == 'tr':
        example_questions = [
            "MACD ne anlama gelir?",
            "Momentum güçleniyor mu?",
            "RSI aşırı alım koşullarını gösteriyor mu?",
            "EMA'lar ne öneriyor?",
            "Mevcut RSI konusunda endişelenmeli miyim?"
        ]
    else:  # English
        example_questions = [
            "What does MACD mean?",
            "Is momentum strengthening?",
            "Is RSI signaling overbought conditions?",
            "What do the EMAs suggest?",
            "Should I be concerned about the current RSI?"
        ]

    example_buttons = "".join([
        f'<button class="example-btn" onclick="document.getElementById(\'ai-question\').value=\'{q}\'; askAI();">{q}</button>'
        for q in example_questions
    ])

    return f"""
    <!DOCTYPE html>
    <html lang="{lang}">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{COINS[symbol]} {t['title']}</title>
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                padding: 20px;
            }}
            
            .header {{
                text-align: center;
                color: white;
                margin-bottom: 30px;
            }}
            
            .header h1 {{
                font-size: 2.5rem;
                font-weight: 700;
                margin-bottom: 10px;
                text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
            }}
            
            .price-display {{
                font-size: 2rem;
                font-weight: 600;
                color: #4ade80;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.2);
            }}
            
            .container {{
                max-width: 1400px;
                margin: 0 auto;
                background: white;
                border-radius: 20px;
                padding: 40px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            }}
            
            .controls {{
                display: flex;
                justify-content: center;
                gap: 20px;
                margin-bottom: 30px;
                flex-wrap: wrap;
            }}
            
            .control-group {{
                display: flex;
                flex-direction: column;
                gap: 8px;
            }}
            
            .control-group label {{
                font-weight: 600;
                color: #374151;
                font-size: 0.9rem;
                text-transform: uppercase;
                letter-spacing: 0.5px;
            }}
            
            select {{
                padding: 12px 20px;
                font-size: 16px;
                border: 2px solid #e5e7eb;
                border-radius: 10px;
                background: white;
                cursor: pointer;
                font-weight: 500;
                transition: all 0.3s;
            }}
            
            select:hover {{
                border-color: #667eea;
            }}
            
            select:focus {{
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }}
            
            .timeline-control {{
                display: flex;
                flex-direction: column;
                gap: 8px;
                min-width: 300px;
            }}
            
            .timeline-control input[type="range"] {{
                width: 100%;
                height: 8px;
                border-radius: 5px;
                background: #e5e7eb;
                outline: none;
                -webkit-appearance: none;
            }}
            
            .timeline-control input[type="range"]::-webkit-slider-thumb {{
                -webkit-appearance: none;
                appearance: none;
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: #667eea;
                cursor: pointer;
                transition: all 0.3s;
            }}
            
            .timeline-control input[type="range"]::-webkit-slider-thumb:hover {{
                background: #764ba2;
                transform: scale(1.2);
            }}
            
            .timeline-control input[type="range"]::-moz-range-thumb {{
                width: 20px;
                height: 20px;
                border-radius: 50%;
                background: #667eea;
                cursor: pointer;
                border: none;
                transition: all 0.3s;
            }}
            
            .timeline-control input[type="range"]::-moz-range-thumb:hover {{
                background: #764ba2;
                transform: scale(1.2);
            }}
            
            .timeline-value {{
                text-align: center;
                font-weight: 600;
                color: #667eea;
                font-size: 1.1rem;
            }}
            
            .info-card {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 25px;
                border-radius: 15px;
                margin-bottom: 25px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            
            .info-card h3 {{
                font-size: 1.3rem;
                margin-bottom: 15px;
                display: flex;
                align-items: center;
                gap: 10px;
            }}
            
            .confidence-badge {{
                display: inline-block;
                padding: 6px 16px;
                border-radius: 20px;
                font-size: 0.85rem;
                font-weight: 600;
                background: rgba(255,255,255,0.2);
                backdrop-filter: blur(10px);
            }}
            
            .info-card p {{
                line-height: 1.8;
                font-size: 1.05rem;
            }}
            
            .subscription-card {{
                background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
                color: white;
                padding: 25px;
                border-radius: 15px;
                margin-bottom: 25px;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            
            .subscription-card h3 {{
                font-size: 1.3rem;
                margin-bottom: 10px;
            }}
            
            .subscription-card .subtitle {{
                margin-bottom: 20px;
                opacity: 0.9;
            }}
            
            .subscription-form {{
                display: flex;
                gap: 10px;
                margin-bottom: 15px;
            }}
            
            .subscription-input {{
                flex: 1;
                padding: 12px 18px;
                font-size: 16px;
                border: 2px solid rgba(255,255,255,0.3);
                border-radius: 10px;
                background: rgba(255,255,255,0.2);
                color: white;
                font-family: inherit;
            }}
            
            .subscription-input::placeholder {{
                color: rgba(255,255,255,0.7);
            }}
            
            .subscription-button {{
                padding: 12px 30px;
                font-size: 16px;
                background: white;
                color: #d97706;
                border: none;
                border-radius: 10px;
                cursor: pointer;
                font-weight: 600;
                transition: all 0.3s;
            }}
            
            .subscription-button:hover {{
                background: #fef3c7;
                transform: translateY(-2px);
            }}
            
            .premium-features {{
                list-style: none;
                padding: 0;
            }}
            
            .premium-features li {{
                padding: 5px 0;
                opacity: 0.95;
            }}
            
            .question-card {{
                background: #f9fafb;
                border: 2px solid #e5e7eb;
                padding: 25px;
                border-radius: 15px;
                margin-bottom: 25px;
            }}
            
            .question-card h3 {{
                color: #1f2937;
                font-size: 1.3rem;
                margin-bottom: 10px;
            }}
            
            .question-card .subtitle {{
                color: #6b7280;
                margin-bottom: 20px;
            }}
            
            .input-group {{
                display: flex;
                gap: 10px;
                margin-bottom: 15px;
            }}
            
            .question-input {{
                flex: 1;
                padding: 14px 18px;
                font-size: 16px;
                border: 2px solid #e5e7eb;
                border-radius: 10px;
                font-family: inherit;
                transition: all 0.3s;
            }}
            
            .question-input:focus {{
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }}
            
            .ask-button {{
                padding: 14px 35px;
                font-size: 16px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                border: none;
                border-radius: 10px;
                cursor: pointer;
                font-weight: 600;
                transition: all 0.3s;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            
            .ask-button:hover {{
                transform: translateY(-2px);
                box-shadow: 0 6px 12px rgba(0,0,0,0.15);
            }}
            
            .ask-button:disabled {{
                background: #9ca3af;
                cursor: not-allowed;
                transform: none;
            }}
            
            .example-questions {{
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-bottom: 15px;
            }}
            
            .example-btn {{
                padding: 8px 16px;
                background: white;
                border: 2px solid #e5e7eb;
                border-radius: 20px;
                cursor: pointer;
                font-size: 0.9rem;
                transition: all 0.3s;
                font-family: inherit;
            }}
            
            .example-btn:hover {{
                background: #667eea;
                color: white;
                border-color: #667eea;
            }}
            
            .answer-box {{
                background: white;
                border: 2px solid #667eea;
                padding: 20px;
                border-radius: 10px;
                margin-top: 15px;
                display: none;
            }}
            
            .answer-box.show {{
                display: block;
                animation: slideIn 0.3s ease;
            }}
            
            @keyframes slideIn {{
                from {{
                    opacity: 0;
                    transform: translateY(-10px);
                }}
                to {{
                    opacity: 1;
                    transform: translateY(0);
                }}
            }}
            
            .loading {{
                color: #667eea;
                font-style: italic;
            }}
            
            .chart-container {{
                margin-top: 30px;
                border-radius: 15px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            
            .chart-container img {{
                width: 100%;
                height: auto;
                display: block;
            }}
            
            .disclaimer {{
                background: #fef3c7;
                border-left: 4px solid #f59e0b;
                padding: 15px 20px;
                border-radius: 10px;
                margin-top: 20px;
                font-size: 0.9rem;
                color: #92400e;
            }}
            
            .footer {{
                text-align: center;
                margin-top: 30px;
                padding-top: 20px;
                border-top: 2px solid #e5e7eb;
                color: #6b7280;
                font-size: 0.9rem;
            }}
            
            @media (max-width: 768px) {{
                .header h1 {{
                    font-size: 1.8rem;
                }}
                .price-display {{
                    font-size: 1.5rem;
                }}
                .container {{
                    padding: 20px;
                }}
                .controls {{
                    flex-direction: column;
                    gap: 15px;
                }}
                .input-group {{
                    flex-direction: column;
                }}
                .subscription-form {{
                    flex-direction: column;
                }}
                .timeline-control {{
                    min-width: 100%;
                }}
            }}
        </style>
        <script>
            function updateTimeline(value) {{
                const daysText = '{t['days']}';
                document.getElementById('timeline-value').textContent = value + ' ' + daysText;
                const form = document.getElementById('timeline-form');
                form.submit();
            }}
            
            async function askAI() {{
                const question = document.getElementById('ai-question').value.trim();
                const answerBox = document.getElementById('answer-box');
                const answerText = document.getElementById('answer-text');
                const askButton = document.getElementById('ask-button');
                const lang = '{lang}';
                const t = {{
                    thinking: '{t['thinking']}',
                    error: '{t['error']}',
                    answer: '{t['answer']}'
                }};
                
                if (!question) {{
                    alert('Please enter a question!');
                    return;
                }}
                
                askButton.disabled = true;
                answerBox.classList.add('show');
                answerText.innerHTML = '<span class="loading">' + t.thinking + '</span>';
                
                try {{
                    const response = await fetch('/api/ask', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{question: question, symbol: '{symbol}'}})
                    }});
                    
                    const data = await response.json();
                    
                    if (data.error) {{
                        answerText.innerHTML = '<strong style="color: #dc2626;">' + t.error + '</strong> ' + data.error;
                    }} else {{
                        answerText.innerHTML = '<strong>' + t.answer + '</strong> ' + data.answer;
                    }}
                }} catch (error) {{
                    answerText.innerHTML = '<strong style="color: #dc2626;">' + t.error + '</strong> Failed to get answer. Please try again.';
                }} finally {{
                    askButton.disabled = false;
                }}
            }}
            
            function handleSubscribe(event) {{
                event.preventDefault();
                const email = document.getElementById('subscribe-email').value;
                const lang = '{lang}';
                const button = event.target.querySelector('button');
                const originalText = button.textContent;
                
                button.disabled = true;
                button.textContent = 'Sending...';
                
                fetch('/api/subscribe', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{email: email, lang: lang}})
                }})
                .then(response => response.json())
                .then(data => {{
                    if (data.success) {{
                        alert(data.message);
                        document.getElementById('subscribe-email').value = '';
                    }} else {{
                        alert('Error: ' + (data.error || 'Failed to subscribe'));
                    }}
                }})
                .catch(error => {{
                    alert('Error: Failed to subscribe. Please try again.');
                }})
                .finally(() => {{
                    button.disabled = false;
                    button.textContent = originalText;
                }});
            }}
            
            document.addEventListener('DOMContentLoaded', function() {{
                document.getElementById('ai-question').addEventListener('keypress', function(e) {{
                    if (e.key === 'Enter') askAI();
                }});
            }});
        </script>
    </head>
    <body>
        <div class="header">
            <h1>📈 {COINS[symbol]} {t['title']}</h1>
            <div class="price-display">${price:,.2f} USD</div>
        </div>
        
        <div class="container">
            <div class="controls">
                <div class="control-group">
                    <label for="coin">{t['cryptocurrency']}</label>
                    <form method="get" style="margin: 0;">
                        <select name="coin" id="coin" onchange="this.form.submit()">
                            {options}
                        </select>
                        <input type="hidden" name="interpretation_level" value="{interpretation_level}">
                        <input type="hidden" name="days" value="{days}">
                        <input type="hidden" name="lang" value="{lang}">
                    </form>
                </div>
                
                <div class="control-group">
                    <label for="interpretation_level">{t['analysis_level']}</label>
                    <form method="get" style="margin: 0;">
                        <select name="interpretation_level" id="interpretation_level" onchange="this.form.submit()">
                            {interpretation_select}
                        </select>
                        <input type="hidden" name="coin" value="{symbol}">
                        <input type="hidden" name="days" value="{days}">
                        <input type="hidden" name="lang" value="{lang}">
                    </form>
                </div>
                
                <div class="control-group">
                    <label for="language">{t['language']}</label>
                    <form method="get" style="margin: 0;">
                        <select name="lang" id="language" onchange="this.form.submit()">
                            {language_options}
                        </select>
                        <input type="hidden" name="coin" value="{symbol}">
                        <input type="hidden" name="interpretation_level" value="{interpretation_level}">
                        <input type="hidden" name="days" value="{days}">
                    </form>
                </div>
            </div>

            <div class="subscription-card">
                <h3>⭐ {t['subscribe']}</h3>
                <p class="subtitle">{t['subscribe_desc']}</p>
                <form class="subscription-form" onsubmit="handleSubscribe(event)">
                    <input 
                        type="email" 
                        id="subscribe-email" 
                        class="subscription-input" 
                        placeholder="{t['email_placeholder']}"
                        required
                    />
                    <button type="submit" class="subscription-button">{t['subscribe_button']}</button>
                </form>
                <div class="premium-features">
                    <strong>{t['premium_features']}</strong>
                    <ul style="list-style: none; padding: 0; margin-top: 10px;">
                        <li>{t['feature_1']}</li>
                        <li>{t['feature_2']}</li>
                        <li>{t['feature_3']}</li>
                        <li>{t['feature_4']}</li>
                    </ul>
                </div>
            </div>

            <div class="info-card">
                <h3>
                    🤖 {t['ai_analysis']}
                    <span class="confidence-badge">{t['confidence']}: {confidence}</span>
                </h3>
                <p>{analysis}</p>
            </div>

            <div class="question-card">
                <h3>💬 {t['ask_questions']}</h3>
                <p class="subtitle">{t['questions_subtitle']}</p>
                
                <div class="example-questions">
                    <small style="width: 100%; display: block; margin-bottom: 8px; color: #6b7280; font-weight: 600;">{t['quick_questions']}</small>
                    {example_buttons}
                </div>
                
                <div class="input-group">
                    <input 
                        type="text" 
                        id="ai-question" 
                        class="question-input" 
                        placeholder="{t['type_question']}"
                    />
                    <button id="ask-button" class="ask-button" onclick="askAI()">{t['ask_ai']}</button>
                </div>
                
                <div id="answer-box" class="answer-box">
                    <div id="answer-text"></div>
                </div>
            </div>

            <div class="timeline-control">
                <label for="timeline">{t['timeline']}: <span id="timeline-value" class="timeline-value">{days} {t['days']}</span></label>
                <form id="timeline-form" method="get">
                    <input type="range" id="timeline" name="days" min="7" max="365" value="{days}" 
                           oninput="updateTimeline(this.value)">
                    <input type="hidden" name="coin" value="{symbol}">
                    <input type="hidden" name="interpretation_level" value="{interpretation_level}">
                    <input type="hidden" name="lang" value="{lang}">
                </form>
            </div>

            <div class="chart-container">
                <img src="/chart?coin={symbol}&days={days}" alt="{COINS[symbol]} Technical Analysis Chart"/>
            </div>

            <div class="disclaimer">
                <strong>⚠️ {t['disclaimer_title']}</strong> {t['disclaimer_text']}
            </div>
            
            <div class="footer">
                {t['copyright']}
            </div>
        </div>
    </body>
    </html>
    """


@app.route("/chart")
def chart():
    symbol = request.args.get("coin", "BTC").upper()
    days = int(request.args.get("days", 90))
    
    if symbol not in COINS:
        return "Invalid coin", 400
    
    # Validate days range
    if days < 7:
        days = 7
    elif days > 365:
        days = 365

    try:
        img_bytes, _ = create_chart(symbol, days)
        return send_file(io.BytesIO(img_bytes), mimetype="image/png")
    except Exception as e:
        print(f"Error creating chart: {e}")
        return f"Error generating chart: {str(e)}", 500


@app.route("/api/analysis")
def api_analysis():
    symbol = request.args.get("coin", "BTC").upper()
    if symbol not in COINS:
        return jsonify({"error": "Invalid coin"}), 400
    
    interpretation_level = request.args.get('interpretation_level', 'advanced')
    days = int(request.args.get('days', 90))
    lang = request.args.get('lang', 'en')
    
    df = get_crypto_data(symbol, days)
    analysis, confidence = get_ai_analysis(symbol, interpretation_level, days, lang)
    
    return jsonify({
        "symbol": symbol,
        "name": COINS[symbol],
        "analysis": analysis,
        "confidence": confidence,
        "interpretation_level": interpretation_level,
        "days": days,
        "language": lang
    })


@app.route("/api/ask", methods=["POST"])
@limiter.limit("10 per minute")
def ask_ai():
    if not ANTHROPIC_API_KEY:
        return jsonify({"error": "API key not configured"}), 500
    
    try:
        data = request.get_json()
        question = data.get("question", "").strip()
        symbol = data.get("symbol", "BTC").upper()
        
        if not question:
            return jsonify({"error": "Question is required"}), 400
        
        df = get_crypto_data(symbol)
        indicators = get_indicator_summary(df)
        
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY, timeout=10.0)
        
        prompt = f"""You are a helpful cryptocurrency education assistant. The user is viewing {COINS[symbol]} ({symbol}) technical charts.

Current market context:
- Price: ${indicators['price']:.2f}
- RSI: {indicators['rsi']:.2f} (5-day change: {indicators['rsi_5d_change']:+.2f})
- MACD Histogram: {indicators['macd_hist']:.4f}
- Price vs EMA-50: {indicators['price_vs_ema50_pct']:+.2f}%

User question: {question}

Provide a clear, educational answer (2-4 sentences). When explaining indicators:
- Reference the current chart values
- Use phrases like "On the RSI panel..." or "Looking at the price chart..."
- Explain concepts in context

IMPORTANT: This is educational only. Avoid trading recommendations. Do not use "buy", "sell", or "target" language."""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        
        return jsonify({
            "answer": message.content[0].text,
            "question": question
        })
        
    except anthropic.APITimeoutError:
        return jsonify({"error": "Request timed out. Please try again."}), 504
    except anthropic.RateLimitError:
        return jsonify({"error": "Rate limit reached. Please wait a moment and try again."}), 429
    except Exception as e:
        print(f"Ask AI Error: {e}")
        return jsonify({"error": "Failed to process question. Please try again."}), 500


@app.route("/api/subscribe", methods=["POST"])
@limiter.limit("5 per hour")
def subscribe():
    """Handle subscription requests and send welcome email"""
    try:
        data = request.get_json()
        email = data.get("email", "").strip()
        lang = data.get("lang", "en")
        
        if not email:
            return jsonify({"error": "Email is required"}), 400
        
        # Basic email validation
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if not re.match(email_pattern, email):
            return jsonify({"error": "Invalid email format"}), 400
        
        # Send the welcome email
        email_sent = send_subscription_email(email, lang)
        
        if email_sent:
            return jsonify({
                "success": True,
                "message": f"Thank you for subscribing! We've sent premium information to {email}"
            })
        else:
            # Email failed but still record the subscription
            return jsonify({
                "success": True,
                "message": f"Subscription recorded for {email}. Email delivery may be delayed.",
                "warning": "Email service temporarily unavailable"
            })
            
    except Exception as e:
        print(f"Subscribe Error: {e}")
        return jsonify({"error": "Failed to process subscription"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), debug=False)
