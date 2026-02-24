import matplotlib
import matplotlib.pyplot as plt
from flask import Flask,render_template , request , make_response,session,redirect,url_for
from datetime import datetime
import pandas as pd
import threading
import sqlite3
import yfinance as yf
from itsdangerous import Signer,BadSignature
import io
import base64
import smtplib
from bs4 import BeautifulSoup
import numpy as np
import asyncio
import plotly.graph_objects as go
import re
from plotly.utils import PlotlyJSONEncoder
import json
import plotly.io as pio
from huggingface_hub import InferenceClient
import requests
import pandas_ta as ta
import plotly.express as px
from flask_caching import Cache
from binance.client import Client
import os
from dotenv import load_dotenv
from email.message import Message,EmailMessage
import time
import ccxt
import ccxt.async_support as ccxt_async
from requests.exceptions import RequestException
import yfinance as yf
from plotly.subplots import make_subplots
from groq import Groq
matplotlib.use('Agg')





app = Flask(__name__)

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))





def zaman_dilimi_kontrol(interval, period):
    zaman_map = {
        '1m': 1, '2m': 2, '5m': 5, '15m': 15, '30m': 30, '60m': 60, '90m': 90,
        '1h': 60,
        '1d': 1440,
        '5d': 7200,
        '1wk': 10080,
        '1mo': 43200,
        '3mo': 129600,
        '6mo': 259200,
        '1y': 525600,
        '2y': 1051200,
        '3y': 1576800,
        '4y': 2102400,
        '5y': 2628000,
        '7y': 3679200,
        '10y': 5256000,
        'ytd': 525600,
        'max': 99999999
    }

    inv_dk = zaman_map.get(interval, 0)
    per_dk = zaman_map.get(period, 0)

    if inv_dk >= per_dk:
        return True
    return False

def veritabani_hazirla():
    conn = sqlite3.connect('alarms_v2.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alarmlar (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                price REAL NOT NULL,
                email TEXT NOT NULL,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        try:
            cursor.execute("ALTER TABLE alarmlar ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except sqlite3.OperationalError:
            pass

        conn.commit()
    finally:
        conn.close()

veritabani_hazirla()
cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache'})
app.secret_key = os.getenv("APP_SECRET_KEY")
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

def mail_gonder(alici, sembol, fiyat):
    msg = EmailMessage()
    msg.set_content(f"🚨 ALARM TETİKLENDİ: {sembol} hedef fiyata ulaştı!\nGüncel Fiyat: ${fiyat}")
    msg['Subject'] = f"CORE_V3 | FİYAT UYARISI: {sembol}"
    msg['From'] = EMAIL_USER
    msg['To'] = alici

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(EMAIL_USER, EMAIL_PASS)
            smtp.send_message(msg)
        print(f">>> Mail gönderildi: {sembol}")
    except Exception as e:
        print(f">>> Mail Hatası: {e}")

import gc



def fiyat_kontrol_dongusu():
    while True:
        try:
            conn = sqlite3.connect('alarms_v2.db')
            cursor = conn.cursor()
            cursor.execute("SELECT id, ticker, price, email FROM alarmlar WHERE status='active'")
            alarmlar = cursor.fetchall()

            for aid, sembol, hedef, email in alarmlar:
                data = yf.Ticker(sembol).fast_info
                anlik_fiyat = data['last_price']

                print(f"Kontrol: {sembol} | Hedef: {hedef} | Anlık: {anlik_fiyat:.2f}")

                fark_yuzde = abs(anlik_fiyat - hedef) / hedef * 100

                if fark_yuzde <= 0.10:
                        mail_gonder(email, sembol, anlik_fiyat)
                        cursor.execute("UPDATE alarmlar SET status='sent' WHERE id=?", (aid,))
                        conn.commit()
                        print(f"🚀 HEDEF YAKALANDI: {sembol} mail gönderildi")

        except Exception as e:
            print(f">>> Gözcü Hatası: {e}")
        finally:
            if conn:
                conn.close()

        time.sleep(60)


@app.route("/alarmlari_listele")
def alarmlari_listele():
    email = request.args.get("email", "").strip()
    veriler = []

    if email:
        conn = sqlite3.connect('alarms_v2.db')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT ticker, price, status, email, id, created_at FROM alarmlar WHERE email = ? ORDER BY id DESC",
            (email,))
        veriler = cursor.fetchall()
        conn.close()

    return render_template("alarm_takip.html", alarmlar=veriler, kullanici_email=email)

@cache.cached(timeout=300)
@app.route('/Finans_Haberleri')
def finans_haberleri():
    haber_url = request.args.get('detay_url')

    if haber_url:
        try:
            headers = {'User-Agent': 'Mozilla/5.0'}
            r = request.get(haber_url, headers=headers, timeout=5)
            soup = BeautifulSoup(r.text, 'html.parser')
            paragraflar = [p.get_text() for p in soup.find_all('p') if len(p.get_text()) > 60]
            ham_metin = "\n\n".join(paragraflar[:12])
            return ham_metin if ham_metin else "Haber içeriği sökülemedi."
        except Exception as e:
            return f"Hata"

    haberler_listesi = []
    try:
        ticker = yf.Ticker('SPY')
        raw_news = ticker.news
        if raw_news and isinstance(raw_news, list):
            for n in raw_news[:30]:
                content = n.get('content', {})
                link_obj = content.get('clickThroughUrl') or content.get('canonicalUrl')
                link = link_obj.get('url') if link_obj else "#"

                haberler_listesi.append({
                    'baslik': content.get('title', 'Başlık Yok'),
                    'kaynak': content.get('provider', {}).get('displayName', 'Bilinmiyor'),
                    'link': link,
                    'zaman': content.get('displayTime', 'Piyasa Haberi')
                })
        return render_template('haberler.html', haberler_listesi=haberler_listesi)
    except Exception as e:
        return f"<h1>Sistem Hatası: {e}</h1>"

@app.route('/Set_Alarm_Giriş')
def set_alarm_giriş():
    return render_template('set_alarm_giriş.html')





@app.route('/set_alarm_kaydet', methods=['POST'])
def set_alarm_kaydet():
    sembol = request.form.get('sembol').upper()
    hedef_fiyat = float(request.form.get('hedef_fiyat'))
    user_email = request.form.get('email').strip()

    try:
        with sqlite3.connect('alarms_v2.db') as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS alarmlar (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    price REAL NOT NULL,
                    email TEXT NOT NULL,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute("""
                INSERT INTO alarmlar (ticker, price, email, status) 
                VALUES (?, ?, ?, 'active')
            """, (sembol, hedef_fiyat, user_email))
            conn.commit()
            print(f">>> Alarm Kaydedildi: {sembol} - {user_email}")

        return redirect(url_for('alarmlari_listele', email=user_email))
    except Exception as e:
        print(f">>> KAYIT HATASI: {e}")
        return f"DATABASE_ERROR: {e}"

@app.route("/alarm_sil/<int:id>")
def alarm_sil(id):
    email = request.args.get("email", "").strip()

    try:
        conn = sqlite3.connect('alarms_v2.db')
        cursor = conn.cursor()
        cursor.execute("DELETE FROM alarmlar WHERE id = ? AND email = ?", (id, email))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Silme Hatası: {e}")

    return redirect(f"/alarmlari_listele?email={email}")




@app.route('/Kar_Zarar_Giriş',methods=['POST','GET'])
def kar_zarar_giriş():
    return render_template('kar_zarar.html')

@app.route("/Kar_Zarar_Hesapla",methods=['POST','GET'])
def kar_zarar_hesapla():
    try:
        miktar = float(request.form.get('miktar'))
        sembol = request.form.get('sembol').upper()
        period = request.form.get('period', '1y')
        interval = '1d' if not period == "max" else '1wk'
        karşılaştırma_varlığı = request.form.get('varlık')

        df = yf.download(sembol, period=period, interval=interval, progress=False,prepost=False)
        if df.empty: return "Veri bulunamadı"

        if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)

        ilk_fiyat = float(df['Close'].values[0])
        son_fiyat = float(df['Close'].values[-1])

        if karşılaştırma_varlığı == "SELF" or not karşılaştırma_varlığı:
            varlık_ilk_fiyat = ilk_fiyat
            varlık_son_fiyat = son_fiyat
        else:
            v_df = yf.download(karşılaştırma_varlığı, period=period, interval=interval, progress=False,prepost=False)
            if v_df.empty: return "Karşılaştırma varlığı verisi bulunamadı"
            if isinstance(v_df.columns, pd.MultiIndex): v_df.columns = v_df.columns.get_level_values(0)
            varlık_ilk_fiyat = float(v_df['Close'].values[0])
            varlık_son_fiyat = float(v_df['Close'].values[-1])

        hisse = yf.Ticker(sembol)
        hisse_basina_miktar = hisse.info.get('dividendRate', 0) or 0
        toplam_adet = miktar / ilk_fiyat
        guncel_deger = float(toplam_adet * son_fiyat)
        başlangıç_varlık_miktarı = miktar / varlık_ilk_fiyat
        elde_kalan_para = guncel_deger - (toplam_adet * ilk_fiyat)
        final_varlik_miktari = guncel_deger / varlık_son_fiyat
        varlik_degisim_farki = final_varlik_miktari - başlangıç_varlık_miktarı
        varlik_bazli_yuzde = ((final_varlik_miktari - başlangıç_varlık_miktarı) / başlangıç_varlık_miktarı) * 100

        try:
            toplam_temettu_geliri = toplam_adet * hisse_basina_miktar
        except:
            toplam_temettu_geliri = 0

        gerçek_kar = float((guncel_deger + (toplam_temettu_geliri or 0)) - miktar)
        kar_orani = (gerçek_kar / miktar) * 100

        return render_template('kar_zarar_hesapla.html', sembol=sembol, baslangic_miktarı=round(miktar, 2),
                               toplam_adet=toplam_adet, ilk_fiyat=ilk_fiyat,
                               son_fiyat=round(son_fiyat, 2),
                               toplam_temettu_geliri=round(toplam_temettu_geliri or 0, 2),
                               gerçek_kar=gerçek_kar, kar_oranı=kar_orani,
                               varlik_bazli_yuzde=varlik_bazli_yuzde, varlik_degisim_farki=varlik_degisim_farki,
                               başlangıç_varlık_miktarı=başlangıç_varlık_miktarı,
                               final_varlik_miktari=final_varlik_miktari, elde_kalan_para=elde_kalan_para)

    except KeyError as e:
        return f"<h1>📊 Veri Formatı Hatası</h1><p>Borsadan gelen verilerde beklenen ... alanı bulunamadı.</p>"
    except requests.exceptions.Timeout:
        return "<h1>⌛ Sunucu Yanıt Vermiyor</h1><p>Veri kaynağı (Yahoo Finance/Borsa) çok geç yanıt veriyor, lütfen tekrar deneyin.</p>"


    except (requests.exceptions.ConnectionError, ConnectionError):
        return "<h1>🌐 Bağlantı Hatası</h1><p>İnternet bağlantınızı kontrol edin veya veri sağlayıcısının erişilebilir olduğundan emin olun.</p>"

    except ZeroDivisionError:
        return "<h1>🧮 Matematiksel Hata</h1><p>Veri setindeki eksiklikler nedeniyle finansal rasyolar hesaplanamadı (Sıfıra bölme hatası).</p>"

    except pd.errors.EmptyDataError:
        return "<h1>📉 Veri Boş</h1><p>Arattığınız hisse/kripto için geçmiş fiyat verisi bulunamadı.</p>"

    except ccxt.ExchangeError:
        return "<h1>🏛️ Borsa API Hatası</h1><p>Kripto borsasından veri çekilirken borsa kaynaklı bir hata oluştu.</p>"

    except ccxt.AuthenticationError:
        return "<h1>🔑 Yetkilendirme Hatası</h1><p>Borsa API anahtarlarınız hatalı veya süresi dolmuş.</p>"

    except PermissionError:
        return "<h1>🔒 Erişim Yetkisi Yok</h1><p>Sistem dosyalarına veya veritabanına erişim izniniz bulunmuyor.</p>"

    except Exception as e:
        return f"<h1>🛠️ Beklenmedik Bir Hata</h1><p>Sistem yöneticisine iletilmek üzere kaydedildi.</p>"


@app.route('/Kripto_Isı_Haritası')
@cache.cached(timeout=150)
def kripto_ısı_haritası():
    try:
        client_binance = Client(api_key="", api_secret="")
        tickers = client_binance.get_ticker()


        kripto_listesi = []

        for coin in tickers:
            sembol = coin['symbol']
            if sembol.endswith('USDT') and not any(x in sembol for x in ['UP', 'DOWN', 'BULL', 'BEAR']):
                try:
                    degisim = float(coin['priceChangePercent'])
                    hacim = float(coin['quoteVolume'])

                    if degisim <= -5:
                        renk = "darkred"
                    elif -5 < degisim <= -2:
                        renk = "red"
                    elif -2 < degisim < 0:
                        renk = "#ff7f7f"
                    elif 0 <= degisim < 2:
                        renk = "#7fff7f"
                    elif 2 <= degisim < 5:
                        renk = "limegreen"
                    else:
                        renk = "darkgreen"

                    kripto_listesi.append({
                        'Coin': sembol.replace('USDT', ''),
                        'Degisim': degisim,
                        'Hacim': hacim,
                        'Renk': renk,
                        'Fiyat': float(coin['lastPrice'])
                    })
                except:
                    continue

        if not kripto_listesi:
            return "<h1>Veri çekilemedi, Binance bağlantısını kontrol edin.</h1>"


        df = pd.DataFrame(kripto_listesi)
        df = df.sort_values(by="Hacim", ascending=False).head(1000)


        df['Gorsel_Boyut'] = df['Hacim'] ** 0.55


        renk_paleti = ["#1e293b"] + df['Renk'].tolist()

        fig = px.treemap(
            df,
            path=[px.Constant("BINANCE TOP 300"), 'Coin'],
            values='Gorsel_Boyut',
            custom_data=['Degisim', 'Hacim', 'Fiyat']
        )

        fig.update_traces(
            marker=dict(
                colors=renk_paleti,
                line=dict(width=1, color='#020617')
            ),
            texttemplate="<b>%{label}</b><br>%{customdata[0]:.2f}%",
            textposition="middle center",
            hovertemplate="<b>%{label}</b><br>Fiyat: $%{customdata[2]}<br>Değişim: %{customdata[0]:.2f}%<br>Hacim: %{customdata[1]:,.0f} USDT<extra></extra>"
        )

        fig.update_layout(
            margin=dict(t=30, l=10, r=10, b=10),
            paper_bgcolor="#020617",
            plot_bgcolor="#020617",
            font=dict(color="white", family="Fira Code"),
            height=1000,
            uniformtext=dict(minsize=6, mode='hide'),
        )

        graph_html = pio.to_html(fig, full_html=False, config={
            'scrollZoom': True,
            'displayModeBar': True,
            'modeBarButtonsToAdd': ['zoomIn2d', 'zoomOut2d', 'pan2d', 'resetScale2d'],
            'displaylogo': False,
            'responsive': True
        })
        return render_template('crypto_heatmap.html', graph_html=graph_html)

    except KeyError as e:
        return f"<h1>📊 Veri Formatı Hatası</h1><p>Borsadan gelen verilerde beklenen ... alanı bulunamadı.</p>"
    except requests.exceptions.Timeout:
        return "<h1>⌛ Sunucu Yanıt Vermiyor</h1><p>Veri kaynağı (Yahoo Finance/Borsa) çok geç yanıt veriyor, lütfen tekrar deneyin.</p>"


    except (requests.exceptions.ConnectionError, ConnectionError):
        return "<h1>🌐 Bağlantı Hatası</h1><p>İnternet bağlantınızı kontrol edin veya veri sağlayıcısının erişilebilir olduğundan emin olun.</p>"

    except ZeroDivisionError:
        return "<h1>🧮 Matematiksel Hata</h1><p>Veri setindeki eksiklikler nedeniyle finansal rasyolar hesaplanamadı (Sıfıra bölme hatası).</p>"

    except pd.errors.EmptyDataError:
        return "<h1>📉 Veri Boş</h1><p>Arattığınız hisse/kripto için geçmiş fiyat verisi bulunamadı.</p>"

    except ccxt.ExchangeError:
        return "<h1>🏛️ Borsa API Hatası</h1><p>Kripto borsasından veri çekilirken borsa kaynaklı bir hata oluştu.</p>"

    except ccxt.AuthenticationError:
        return "<h1>🔑 Yetkilendirme Hatası</h1><p>Borsa API anahtarlarınız hatalı veya süresi dolmuş.</p>"

    except PermissionError:
        return "<h1>🔒 Erişim Yetkisi Yok</h1><p>Sistem dosyalarına veya veritabanına erişim izniniz bulunmuyor.</p>"

    except Exception as e:
        print(e)
        return f"<h1>🛠️ Beklenmedik Bir Hata</h1><p>Sistem yöneticisine iletilmek üzere kaydedildi.</p>"
    finally:
        if client_binance is not None:
            try:
                client_binance.close()
            except:
                pass
            del client_binance
        if df is not None:
            del df
        if kripto_listesi is not None:
            del kripto_listesi
        if tickers is not None:
            del tickers
        if fig is not None:
            del fig
        if graph_html is not None:
            del graph_html
        gc.collect()
        gc.collect(generation=2)


@app.route("/")
def selamün_aleyküm():
    try:
        hisse_sozluk = {
            "^GSPC": "S&P 500", "^DJI": "Dow Jones", "^IXIC": "NASDAQ",
            "NQ=F": "Nasdaq Futures", "^NYA": "NYSE", "AAPL": "Apple", "GC=F": "Gold (ONS)", "SI=F": "Silver (ONS)",
            'PA=F': 'Palladium (ONS)', 'CL=F': 'Texas Oil',
            "TSLA": "Tesla", "NVDA": "NVIDIA", "XU100.IS": "BIST 100", "XBANK.IS": "BIST Banka", 'BZ=F': 'Brent Oil',
            'USDTRY=X': 'USD/TRY', "EURTRY=X": 'EUR/TRY', 'GBPTRY=X': 'GBP/TRY', 'CADTRY=X': 'CAD/TRY','USDEUR=X':'USD/EUR'

        }

        ticker_verileri = []

        ticker_listesi = list(hisse_sozluk.keys())
        data = yf.download(ticker_listesi, period='2d', interval='15m', group_by='ticker', progress=False,prepost=False)

        for ticker in ticker_listesi:
            try:
                hisse_verisi = data[ticker].dropna()

                if not hisse_verisi.empty:
                    ilk_fiyat = float(hisse_verisi['Close'].iloc[0])
                    son_fiyat = float(hisse_verisi['Close'].iloc[-1])
                    degisim = ((son_fiyat - ilk_fiyat) / ilk_fiyat) * 100

                    ticker_verileri.append({
                        "sembol": ticker,
                        "isim": hisse_sozluk[ticker],
                        "fiyat": round(son_fiyat, 2),
                        "degisim": round(degisim, 2),
                        "renk": "#00ffbb" if degisim >= 0 else "#ff4b5c"
                    })
            except:
                continue

        return render_template("hello.html", ticker_data=ticker_verileri)
    except KeyError as e:
        return f"<h1>📊 Veri Formatı Hatası</h1><p>Borsadan gelen verilerde beklenen ... alanı bulunamadı.</p>"
    except requests.exceptions.Timeout:
        return "<h1>⌛ Sunucu Yanıt Vermiyor</h1><p>Veri kaynağı (Yahoo Finance/Borsa) çok geç yanıt veriyor, lütfen tekrar deneyin.</p>"


    except (requests.exceptions.ConnectionError, ConnectionError):
        return "<h1>🌐 Bağlantı Hatası</h1><p>İnternet bağlantınızı kontrol edin veya veri sağlayıcısının erişilebilir olduğundan emin olun.</p>"

    except ZeroDivisionError:
        return "<h1>🧮 Matematiksel Hata</h1><p>Veri setindeki eksiklikler nedeniyle finansal rasyolar hesaplanamadı (Sıfıra bölme hatası).</p>"

    except pd.errors.EmptyDataError:
        return "<h1>📉 Veri Boş</h1><p>Arattığınız hisse/kripto için geçmiş fiyat verisi bulunamadı.</p>"

    except ccxt.ExchangeError:
        return "<h1>🏛️ Borsa API Hatası</h1><p>Kripto borsasından veri çekilirken borsa kaynaklı bir hata oluştu.</p>"

    except ccxt.AuthenticationError:
        return "<h1>🔑 Yetkilendirme Hatası</h1><p>Borsa API anahtarlarınız hatalı veya süresi dolmuş.</p>"

    except PermissionError:
        return "<h1>🔒 Erişim Yetkisi Yok</h1><p>Sistem dosyalarına veya veritabanına erişim izniniz bulunmuyor.</p>"

    except Exception as e:
        print(e)
        return f"<h1>🛠️ Beklenmedik Bir Hata</h1><p>Sistem yöneticisine iletilmek üzere kaydedildi.</p>"



async def fetch_exchange_data(ex_id, symbol, coin):
    exchange = None
    try:
        # Borsa bağlantısını asenkron başlat
        exchange = getattr(ccxt_async, ex_id)({
            'timeout': 3000,
            'enableRateLimit': True
        })

        ticker = await exchange.fetch_ticker(symbol)
        price = float(ticker['last'])

        fee = 0
        try:
            currencies = await exchange.fetch_currencies()
            if coin in currencies:
                fee = float(currencies[coin].get('fee', 0))
        except:
            pass

        return {"exchange": ex_id.capitalize(), "price": price, "fee": fee}
    except:
        return None
    finally:
        if exchange:
            await exchange.close()


async def get_multi_exchange_arbitrage_async(coin, is_crypto=True):
    if not is_crypto:
        return {
            "is_available": False,
            "not": "ℹ️ Arbitraj analizi sadece kripto paralar için geçerlidir. Hisse senetleri ve emtialar merkezi borsalarda işlem gördüğü için bu varlıklarda arbitraj imkanı bulunmamaktadır."
        }

    exchanges_list = [
        'binance', 'gateio', 'okx', 'bybit', 'kucoin',
        'kraken', 'bitget', 'mexc', 'huobi', 'bitfinex',
        'coinbase', 'whitebit', 'phemex', 'lbank', 'bingx'
    ]

    symbol = f"{coin}/USDT"
    results = []
    for ex_id in exchanges_list:
        try:
            await asyncio.sleep(0.2)

            res = await fetch_exchange_data(ex_id, symbol, coin)

            if res:
                results.append(res)
                print(f"DEBUG: {ex_id} fiyatı alındı.")
        except Exception as e:
            print(f"DEBUG: {ex_id} hatası -> {e}")

        try:
            prices = [r for r in results if r is not None]

            if not prices or len(prices) < 2:
                return {
                    "is_available": False,
                    "not": f"⚠️ Borsalardan fiyat çekilemedi. (Sembol: {symbol})"
                }

            min_p = min(prices, key=lambda x: x['price'])
            max_p = max(prices, key=lambda x: x['price'])
        except:
            max_p = None
            min_p = None

    brut_fark_yuzde = ((max_p['price'] - min_p['price']) / min_p['price']) * 100

    target_fee = min_p.get('fee', 0) if min_p.get('fee') is not None else 0
    masraf_usd = target_fee * min_p['price']
    net_fark_usd = (max_p['price'] - min_p['price']) - masraf_usd
    net_yuzde = (net_fark_usd / min_p['price']) * 100

    if net_yuzde > 1.5:
        not_metni = f"🔥 KRİTİK FIRSAT: %{round(net_yuzde, 2)} Net Kâr! {min_p['exchange']} -> {max_p['exchange']}"
    elif net_yuzde > 0.5:
        not_metni = f"✅ MAKUL: %{round(net_yuzde, 2)} Net Kâr saptandı."
    elif net_yuzde <= 0 and brut_fark_yuzde > 0:
        not_metni = f"⚠️ TUZAK: %{round(brut_fark_yuzde, 2)} brüt fark var ama çekim ücretleri kârı sıfırlıyor."
    else:
        not_metni = "⚖️ DENGELİ: Borsalar arası fark arbitraj masraflarını karşılamıyor."

    return {
        "is_available": True,
        "all_prices": sorted(prices, key=lambda x: x['price'], reverse=True),
        "best_deal": {
            "buy_from": min_p['exchange'],
            "buy_price": min_p['price'],
            "sell_to": max_p['exchange'],
            "sell_price": max_p['price'],
            "brut_yuzde": round(brut_fark_yuzde, 4),
            "net_yuzde": round(net_yuzde, 4),
            "fee_usd": round(masraf_usd, 2),
            "not": not_metni
        }
    }

@app.route("/Finans")
def finans():
    return render_template("finans_menu.html")

@app.route('/Isı_Grafiği_Giriş',methods=['POST','GET'])
def hisse_ısı_haritası_başlangıç():
    return render_template("hisse_ısı.html")

@app.route('/Graphia_Hisse_Isı_Haritası',methods=['POST','GET'])
@cache.cached(timeout=300,query_string=True)
def hisse_ısı_haritası():
    try:
        nasdaq_300_hisseleri = [
            "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA", "BRK-B", "UNH",
            "LLY", "JPM", "XOM", "V", "MA", "AVGO", "HD", "PG", "COST", "JNJ",
            "ABBV", "MRK", "CRM", "BAC", "ADBE", "NFLX", "AMD", "PEP", "KO", "TMO",
            "WMT", "CVX", "DIS", "CSCO", "ACN", "ABT", "LIN", "ORCL", "INTU", "QCOM",
            "TXN", "AMAT", "DHR", "GE", "VZ", "AMGN", "PFE", "UNP", "LOW", "HON",
            "IBM", "PM", "CAT", "GS", "ISRG", "MS", "RTX", "BA", "BKNG", "SPGI",
            "UPS", "SYK", "LMT", "DE", "TJX", "BLK", "NOW", "AXP", "MDLZ", "VRTX",
            "ADI", "REGN", "ADP", "PLD", "ETN", "MU", "SNPS", "CDNS", "ELV", "CI",
            "BSX", "ZTS", "MCD", "EOG", "SLB", "WM", "ITW", "CVS", "BDX", "MO",
            "USB", "T", "MMC", "PH", "GD", "MDT", "PGR", "HCA", "ORLY", "MAR",
            "MCK", "CL", "NSC", "AON", "EMR", "APD", "BSX", "F", "GM", "FCX",
            "MET", "AIG", "D", "ED", "SO", "DUK", "SRE", "AEP", "WM", "VRSK",
            "IT", "CTAS", "ROP", "PAYX", "EL", "KDP", "STZ", "MNST", "ADM", "CPB",
            "K", "GIS", "SYY", "KR", "WBA", "TGT", "TJX", "ROST", "DLTR", "DG",
            "AZO", "GPN", "FI", "JKHY", "V", "MA", "AXP", "DFS", "COF", "PYPL",
            "PANW", "FTNT", "CRWD", "OKTA", "ZS", "DDOG", "TEAM", "MDB", "SNOW", "NET",
            "PATH", "U", "PLTR", "AI", "SMCI", "ARM", "ASML", "LRCX", "KLAC", "MCHP",
            "ON", "MPWR", "NXPI", "SWKS", "QRVO", "ALGN", "IDXX", "IQV", "HCA", "HUM",
            "CNC", "MOH", "CI", "CVS", "GEHC", "DHR", "TMO", "A", "WAT", "MTD",
            "ZBH", "SYK", "EW", "BSX", "MDT", "BAX", "DXCM", "PODD", "BIIB", "AMGN",
            "MRNA", "GILD", "REGN", "VRTX", "ILMN", "EXC", "XEL", "PEG", "WEC", "ES",
            "EIX", "FE", "DTE", "ETR", "AEE", "LNT", "CNP", "CMS", "NI", "PNW",
            "NRG", "VST", "CEG", "AWK", "PSA", "PLD", "AMT", "CCI", "EQIX", "SBAC",
            "DLR", "VICI", "WY", "SPG", "CBRE", "AVB", "EQR", "MAA", "UDR", "ESS",
            "CPRT", "ODFL", "CSX", "UNP", "NSC", "FDX", "UPS", "LUV", "DAL", "UAL",
            "AAL", "MAR", "HLT", "BKNG", "EXPE", "ABNB", "TRV", "CB", "PGR", "ALL",
            "MET", "PRU", "AFL", "GL", "AJG", "WTW", "BRO", "MMC", "AON", "MCO"
        ]
        period = request.args.get('period', '1d')

        intervals = {
            "1d": "1h",
            "1wk": "1h",
            "1mo": "1d",
            "6mo": "1d",
            "1y": "1d",
            "max": "1wk"
        }
        interval = intervals.get(period, "1h")

        df = yf.download(nasdaq_300_hisseleri, period=period, interval=interval, progress=False, threads=5,prepost=False)
        hisse_listesi, degisim_listesi, hacim_listesi, renk_listesi, fiyat_listesi = [], [], [], [], []

        for hisse in nasdaq_300_hisseleri:
            try:
                if hisse not in df['Close'] or df['Close'][hisse].dropna().empty:
                    continue

                kapanis = float(df['Close'][hisse].dropna().iloc[-1])
                acilis = float(df['Open'][hisse].dropna().iloc[0])
                hacim = float(df['Volume'][hisse].dropna().iloc[-1])

                if pd.isna(kapanis) or pd.isna(acilis) or hacim <= 0:
                    continue

                yuzdelik_degisim = (kapanis - acilis) / acilis * 100

                # Renk Hesaplaması
                if yuzdelik_degisim <= -3:
                    renk = "#8b0000"
                elif yuzdelik_degisim < 0:
                    renk = "#ff4b5c"
                elif yuzdelik_degisim < 3:
                    renk = "#00ffbb"
                else:
                    renk = "#006400"

                hisse_listesi.append(hisse)
                degisim_listesi.append(yuzdelik_degisim)
                hacim_listesi.append(hacim)
                fiyat_listesi.append(kapanis)
                renk_listesi.append(renk)
            except:
                continue

        if not hisse_listesi:
            return "Veri çekilemedi, borsa kapalı olabilir."

        # Görsel boyut için logaritmik hesaplama
        final_df = pd.DataFrame({
            "Hisse": hisse_listesi,
            "Degisim": degisim_listesi,
            "Hacim": hacim_listesi,
            "Renk": renk_listesi,
            "Fiyat": fiyat_listesi,
            "Boyut": [h ** 0.55 for h in hacim_listesi]
        })

        final_df['Gorsel_Boyut'] = final_df['Hacim'] ** 0.90

        fig = px.treemap(
            final_df,
            path=[px.Constant("NASDAQ 300"), 'Hisse'],
            values='Gorsel_Boyut',
            custom_data=['Degisim', 'Hacim', 'Fiyat']
        )

        fig.update_layout(
            paper_bgcolor="#05070a",
            plot_bgcolor="#05070a",
            font=dict(color="white", family="Fira Code"),
            margin=dict(t=30, l=10, r=10, b=10)
        )

        fig.update_traces(
            marker=dict(colors=final_df['Renk'], line=dict(width=1, color='#0f172a')),
            texttemplate="<b>%{label}</b><br>%{customdata[0]:.2f}%",
            hovertemplate="<b>%{label}</b><br>Değişim: %{customdata[0]:.2f}%<br>Fiyat: %{customdata[2]:.2f}$<extra></extra>"
        )

        config = {
            'scrollZoom': True,
            'displayModeBar': True,
            'modeBarButtonsToAdd': ['zoomIn2d', 'zoomOut2d', 'pan2d', 'resetScale2d'],
            'displaylogo': False,
            'responsive': True
        }

        graph_html = pio.to_html(fig, full_html=False, config=config)
        return render_template("heatmap.html", graph_html=graph_html)
    except Exception:
        return "<h1>Bir Hata Oluştu </h1>"
    finally:
        if df is not None:
            del df
        if final_df is not None:
            del final_df
        listeler = [
            'hisse_listesi', 'degisim_listesi', 'hacim_listesi',
            'renk_listesi', 'fiyat_listesi', 'renk_paleti'
        ]
        for var_name in listeler:
            if var_name in locals() and locals()[var_name] is not None:
                try:
                    del locals()[var_name]
                except:
                    pass
        if fig is not None:
            del fig
        if graph_html is not None:
            del graph_html
        gc.collect()
        gc.collect(generation=2)

@app.route("/Finance",methods=['POST'])
def Finance():
    try:
        sembol = request.form.get('hisse').upper()
        Dil = request.form.get('Dil')
        tarih = "Bilinmiyor"
        veri = yf.Ticker(sembol)
        gecmis_ = veri.history(period="5d")
        net_kar_marjı = np.nan
        en_yuksek = np.nan
        defter_değeri = np.nan
        borç_bölü_özkaynak_oran = np.nan
        durum = "Veri Yok"
        yüzde_sahiplik = np.nan
        sahiplik_durum = "Veri Yok"
        cari_oran = np.nan
        cari_durum = "Veri Yok"
        adx_yön = "N/A"
        max_p = 0
        indikatör = "N/A"
        renk = "warning"
        güven_mesajı = "Veri Alınamadı"

        halka_arz_tarihi = "N/A"
        adres = "Bilinmiyor"
        web_sitesi = "N/A"
        çalışan_sayısı = np.nan
        gelir_bölü_çalışan = np.nan
        halka_arz = np.nan
        kuruluş_yılı = "N/A"
        iştah = "Nötr"
        renk = "secondary"
        güven_mesajı = "Analiz Ediliyor..."
        peg_durum = "Veri Yok"
        insider_mesajı = "Veri Yok"
        öneriler = []
        ema_listesi_tablo = []
        ema_listesi_sözlük = {}
        long_name = sembol
        bilanço_tarihi = "N/A"
        bilanço_beklenti = "N/A"
        öz_kaynak_karlılığı = np.nan
        fk_oran = np.nan
        beta = np.nan
        hacim = 0
        ortalama_hacim = 0
        defter_değeri = "Bu Varlık İçin Mevcut Değil"

        long_name = "Bilinmeyen Varlık"
        if not sembol:
            return "Hisse Kısmı Boş Olamaz"

        try:
            df = yf.download(sembol, period="5d", interval="1d", progress=False,prepost=False)
        except:
            df = pd.DataFrame()

        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

            if "=X" in sembol or "TRY" in sembol or "USD" in sembol:
                hbk = np.nan
                hisse_başına_kar = np.nan
                peg_ratio = np.nan
                peg_durum = "Kripto/Döviz için geçerli değil"
                FAVÖK = np.nan
                net_kar_marjı = np.nan
                borç_bölü_özkaynak_oran = np.nan
                borç_bölü_özkaynak_oranı = np.nan
                cari_oran = np.nan
                cari_durum = "Bilanço verisi yok"
                öz_kaynak_karlılığı = np.nan
                likite_durumu = "N/A"


                ceo = "Merkeziyetsiz / N/A"
                çalışan_sayısı = np.nan
                gelir_bölü_çalışan = np.nan
                kuruluş_yılı = "N/A"
                adres = "Dijital Varlık"
                web_sitesi = "N/A"
                halka_arz = np.nan
                halka_arz_tarihi = np.nan
                halka_arz_fiyatı = np.nan
                long_name = sembol


                yüzde_sahiplik = np.nan
                kurumsal_sahiplik = np.nan
                sahiplik_durum = "Veri Yok"
                short_interest = np.nan
                short_ratio = np.nan
                durum = "N/A"
                insider_mesajı = "İçeriden alım verisi bulunmuyor"
                toplam_hisse_sayısı = np.nan
                market_cap = np.nan

                hedef_fiyat = np.nan
                tavsiye = "N/A"
                potansiyel = np.nan
                bilanço_tarihi = "Yok"
                bilanço_beklenti = "N/A"
                temettü = np.nan
                temettü_verimi = np.nan
                iştah = "Piyasa Verisi"
                güven_mesajı = "Teknik Analiz Görünümü"
                renk = "warning"
                long_name = np.nan
                kar = np.nan
                kurumsal_yatırımcılar_sahiplik_oranı = np.nan
                bilanço_tarihi = "Yok"
                bilanço_verisi = np.nan

                ema_df = veri.history(period="1y")
                if not ema_df.empty:
                    if isinstance(ema_df.columns, pd.MultiIndex):
                        ema_df.columns = ema_df.columns.get_level_values(0)


                ema_listesi_sözlük = {}
                ema_listesi_tablo = []
                periyotlar = range(20, 220, 20)
                son_fiyat = ema_df['Close'].iloc[-1]
                alış_sinyali = 0
                satış_sinyali = 0
                alış_sinyali_sma = 0
                satış_sinyali_sma = 0
                öneriler = pd.DataFrame()
                for p in periyotlar:
                    sütun_adı = f"EMA-{p}"
                    sma_sütun_adı = f"SMA-{p}"
                    ema_değeri = ema_df['Close'].ewm(span=p, adjust=False).mean()
                    sma_değeri = ema_df['Close'].rolling(window=p).mean()
                    güncel_sma = float(sma_değeri.iloc[-1])
                    güncel_ema = float(ema_değeri.iloc[-1])
                    ema_listesi_sözlük[sütun_adı] = round(güncel_ema, 2)

                    if son_fiyat > güncel_ema:
                        alış_sinyali += 1
                    elif son_fiyat == güncel_ema:
                        alış_sinyali += 0
                        satış_sinyali += 0
                    else:
                        satış_sinyali += 1

                    if son_fiyat > güncel_sma:
                        alış_sinyali_sma += 1
                    elif son_fiyat == güncel_sma:
                        alış_sinyali_sma += 0
                        satış_sinyali_sma += 0
                    else:
                        satış_sinyali_sma += 1

                    if alış_sinyali > 7:
                        gösterge = "Güçlü Al"
                        ema_renk = "Succes"
                    elif alış_sinyali > 5:
                        gösterge = "Al"
                        ema_renk = "Succes"
                    elif satış_sinyali > 7:
                        gösterge = "Güçlü Sat"
                        ema_renk = "danger"
                    elif satış_sinyali > 5:
                        gösterge = "Sat"
                        ema_renk = "danger"
                    else:
                        gösterge = "NÖTR/BEKLE"
                        ema_renk = "warning"

                    if alış_sinyali_sma > 7:
                        sma_gösterge = "Güçlü Al"
                        sma_renk = "succes"
                    elif alış_sinyali_sma > 5:
                        sma_gösterge = "Al"
                        sma_renk = "succes"
                    else:
                        sma_gösterge = "Nötr/Bekle"
                        sma_renk = 'warning'

                    if satış_sinyali_sma > 7:
                        sma_gösterge = "Güçlü Sat"
                        sma_renk = "danger"
                    elif satış_sinyali_sma > 5:
                        sma_gösterge = "Güçlü Sat"
                        sma_renk = "danger"
                    else:
                        sma_gösterge = "Nötr/Bekle"
                        sma_renk = 'warning'

                    ema_listesi_tablo.append({
                        'periyot': f"EMA-{p}",
                        'deger': güncel_ema,
                        'sinyal_ema': gösterge,
                        'sinyal_sma': sma_gösterge,
                        'sma_renk': sma_renk,
                        'renk': ema_renk
                    })
                    insider_verisi = np.nan
                    skor = 0
                    güven_mesajı = "Teknik Analiz Görünümü"
                    cari_durum = "Emtia/Döviz verisinde Cari Oran bulunmaz."
                    öz_kaynak_karlılığı = np.nan
                    peg_durum = "Emtia verisinde PEG rasyosu bulunmaz."
                    ma_sinyal = "Grafik verileri üzerinden takip edilmeli."
                    insider_mesajı = "Kurumsal Insider verisi bu varlık için geçerli değil."
                    en_yüksek = df['High'].max()

                    sektör = "Bilinmiyor"
                    potansiyel = 0.0
                    KRİPTO_EVRENİ = [
                        'BTC', 'ETH', 'BNB', 'SOL', 'XRP',
                        'ADA', 'DOT', 'AVAX', 'NEAR', 'ATOM', 'ALGO', 'SUI', 'APT', 'SEI',
                        'MATIC', 'OP', 'ARB', 'LDO',
                        'FET', 'RNDR', 'GRT', 'ICP', 'LINK',
                        'DOGE', 'SHIB', 'PEPE', 'WIF', 'BONK',
                        'UNI', 'AAVE'
                    ]
                    temiz_sembol = sembol.replace("-USD", "").split('/')[0].strip().upper()
                    if temiz_sembol in KRİPTO_EVRENİ:
                        hacim = df['Volume'].iloc[-1]
                        ortalama_hacim = df['Volume'].mean()
                    else:
                        hacim = np.nan
                        ortalama_hacim = np.nan
                    veri_ath = yf.download(sembol, period='max', interval="1d",progress=False,prepost=False)
                    if isinstance(veri_ath.columns, pd.MultiIndex):
                        veri_ath.columns = veri_ath.columns.get_level_values(0)
                    en_dusuk = float(veri_ath['Close'].min())

                    ATH = veri_ath['Close'].max()
                    kapanıs_ath = veri_ath['Close'].iloc[-1]
                    zirveden_uzaklık = ((kapanıs_ath - ATH) / ATH) * 100
                    kapanıs = kapanıs_ath


                    if long_name is np.nan or not long_name:
                        long_name = sembol
                    ai_analiz_notu = "Bu bir döviz/emtia varlığıdır. AI analizi teknik göstergelere göre hazırlanacaktır."
                    rol_tanımı = f"Bu Bir Emtia veya Döviz Parametresidir Bu parametreyi Derinlemesine İncele Ve Verileri Tekrar etmeden kullanıcya çok detaylı ve açıklayıcı bir şekilde varığın durumunu analiz et ve potansiyel fırsatları anlat ve en sonunda geleceği hakkına kendi yorumlarını yaz VE YORUMUN TAMAMINI {Dil} DİLİNDE YAZ"

            else:
                fiyat = df.iloc[-1]
                tarih = df.index[-1].strftime("%Y.%m.%d")
                hacim = fiyat['Volume']
                ortalama_hacim = fiyat['Volume'].mean()
                en_yuksek = df['High'].max()
                en_dusuk = df['Low'].min()
                kapanıs = float(df['Close'].iloc[-1])
                beta = veri.info.get('Beta')
                market_cap = veri.info.get('marketCap')
                temettü = veri.info.get('dividendYield')
                temettü_verimi = veri.info.get('trailingAnnualDividendYield')
                toplam_hisse_sayısı = veri.info.get("sharesOutstanding")
                max_geçmiş = veri.history(period="max", auto_adjust=False, actions=False)
                öz_kaynak_karlılığı = veri.info.get("returnOnEquity")
                defter_değeri = veri.info.get('priceToBook')
                borç_bölü_özkaynak_oran = veri.info.get('debtToEquity')
                short_ratio = veri.info.get('shortRatio', np.nan)
                df_adx = yf.download(sembol,period="15d",interval="1h",progress=False,prepost=False)

                if isinstance(df_adx.columns,pd.MultiIndex):
                    df_adx.columns = df_adx.columns.get_level_values(0)

                df_adx.ta.adx(append=True)
                güncel_adx = round(df_adx['ADX_14'].iloc[-1],2)
                güncel_di_plus = round(df_adx['DMP_14'].iloc[-1],2)
                güncel_di_minüs = round(df_adx['DMN_14'].iloc[-1],2)

                if güncel_adx > 25:
                    adx_yön = "YUKARI (ALICILAR HAKİM)" if güncel_di_plus > güncel_di_minüs else "AŞAĞI (SATICILAR HAKİM)"
                    adx_trend = "Güçlü Trend"
                else:
                    adx_trend = "Zayıf/Yatay Piyasa"
                    adx_yön = "Belirsiz / Testere"


                haber_metni = ""
                try:
                    son_haberler = veri.news[:-5]
                    for haber in son_haberler:
                        haber_metni += f"- {haber['title']}\n"
                except:
                    haberler_metni = "Güncel Haberler Bulunmadı"


                kurumsal_yatırımcılar_sahiplik_oranı = veri.info.get('heldPercentInstitutions')
                adres = veri.info.get('address1')
                çalışan_sayısı = veri.info.get("fullTimeEmployees")
                officers = veri.info.get('companyOfficers')
                if officers:
                    ceo = veri.info.get('companyOfficers', )[0]['name']
                else:
                    ceo = "Bilinmiyor"
                gelir = veri.info.get('totalRevenue', np.nan)
                if gelir is not None and çalışan_sayısı is not None and çalışan_sayısı > 0:
                    gelir_bölü_çalışan = gelir / çalışan_sayısı
                else:
                    gelir_bölü_çalışan = np.nan
                halka_arz_ms = veri.info.get('firstTradeDateMilliseconds')
                geçmiş_hepsi = veri.history(period="max", interval="1d")
                özet = veri.info.get("longBusinnesSummary")
                try:
                    öneriler = veri.recommendations
                except:
                    öneriler = []
                long_name = veri.info.get('longName')
                bilanço_tarihi = "Belirtilmemiş"
                bilanço_beklenti = "Veri Yok"
                kar = veri.earnings_dates
                veri_ath = yf.download(sembol, period="max", interval="1d", progress=False,prepost=False)
                veri_ath = pd.DataFrame(veri_ath)
                if isinstance(veri_ath.columns, pd.MultiIndex):
                    veri_ath.columns = veri_ath.columns.get_level_values(0)
                ATH = float(veri_ath['Close'].max())
                if kar is not None and not kar.empty:
                    future_earnings = kar[kar.index > pd.Timestamp.now(tz='UTC')]
                    if not future_earnings.empty:
                        en_yakın_bilanço = future_earnings.iloc[0]
                        bilanço_tarihi = en_yakın_bilanço.strftime("%Y,%m-%d")
                        bilanço_beklenti = future_earnings.iloc[0].get('EPS Estimate')
                        if pd.notnull(bilanço_beklenti):
                            bilanço_beklenti = bilanço_beklenti

                ema_df = veri.history(period="1y")
                if not ema_df.empty:
                    if isinstance(ema_df.columns, pd.MultiIndex):
                        ema_df.columns = ema_df.columns.get_level_values(0)

                ema_listesi_sözlük = {}
                ema_listesi_tablo = []
                rol_tanımı = f"Sen kıdemli bir borsa analistisin. Sadece TÜRKÇE konuş. Verilen parametrelere göre hissenin risk ve fırsatlarını çok uzunca değerlendir. Ayrıca Çok Detaylı Olarak Şirketin Sektör Bilgisinden Yola Çıkarak FK oranını buna göre değerlendir ayrıca haberlerden yola çıkarak haberlerin hisseyle ilgili neleri işaret ettiğnide anlat  VE YORUMUN TAMAMINI {Dil} DİLİNDE YAZ"
                periyotlar = range(20, 220, 20)
                son_fiyat = ema_df['Close'].iloc[-1]
                sektör = veri.info.get('Sektör')
                alış_sinyali = 0
                satış_sinyali = 0
                alış_sinyali_sma = 0
                satış_sinyali_sma = 0
                for p in periyotlar:
                    sütun_adı = f"EMA-{p}"
                    sma_sütun_adı = f"SMA-{p}"
                    ema_değeri = ema_df['Close'].ewm(span=p, adjust=False).mean()
                    sma_değeri = ema_df['Close'].rolling(window=p).mean()
                    güncel_sma = float(sma_değeri.iloc[-1])
                    güncel_ema = float(ema_değeri.iloc[-1])
                    ema_listesi_sözlük[sütun_adı] = round(güncel_ema, 2)

                    if son_fiyat > güncel_ema:
                        alış_sinyali += 1
                    elif son_fiyat == güncel_ema:
                        alış_sinyali += 0
                        satış_sinyali += 0
                    else:
                        satış_sinyali += 1

                    if son_fiyat > güncel_sma:
                        alış_sinyali_sma += 1
                    elif son_fiyat == güncel_sma:
                        alış_sinyali_sma += 0
                        satış_sinyali_sma += 0
                    else:
                        satış_sinyali_sma += 1

                    if alış_sinyali > 7:
                        gösterge = "Güçlü Al"
                        ema_renk = "Succes"
                    elif alış_sinyali > 5:
                        gösterge = "Al"
                        ema_renk = "Succes"
                    elif satış_sinyali > 7:
                        gösterge = "Güçlü Sat"
                        ema_renk = "danger"
                    elif satış_sinyali > 5:
                        gösterge = "Sat"
                        ema_renk = "danger"
                    else:
                        gösterge = "NÖTR/BEKLE"
                        ema_renk = "warning"

                    if alış_sinyali_sma > 7:
                        sma_gösterge = "Güçlü Al"
                        sma_renk = "succes"
                    elif alış_sinyali_sma > 5:
                        sma_gösterge = "Al"
                        sma_renk = "succes"
                    else:
                        sma_gösterge = "Nötr/Bekle"
                        sma_renk = 'warning'

                    if satış_sinyali_sma > 7:
                        sma_gösterge = "Güçlü Sat"
                        sma_renk = "danger"
                    elif satış_sinyali_sma > 5:
                        sma_gösterge = "Güçlü Sat"
                        sma_renk = "danger"
                    else:
                        sma_gösterge = "Nötr/Bekle"
                        sma_renk = 'warning'

                    ema_listesi_tablo.append({
                        'periyot': f"EMA-{p}",
                        'deger': güncel_ema,
                        'sinyal_ema': gösterge,
                        'sinyal_sma': sma_gösterge,
                        'sma_renk': sma_renk,
                        'renk': ema_renk
                    })

                if öneriler is not None and len(öneriler) >0:
                    if isinstance(öneriler,pd.DataFrame):
                        son_öneriler = öneriler.tail(5)
                    else:
                        son_öneriler = öneriler[-5:]
                if özet:
                    kuruluş_yılı_bul = re.search(r"founded in (\d{4})", özet)
                    if kuruluş_yılı_bul:
                        kuruluş_yılı = kuruluş_yılı_bul.group(1)
                    else:
                        kuruluş_yılı = "Belirtilmemiş"
                else:
                    kuruluş_yılı = "Bilgi Yok"
                beklenen_hbk = veri.info.get('epsForward')
                likitide_oranı = veri.info.get('quickRatio')
                if likitide_oranı and likitide_oranı is not None:
                    if likitide_oranı >= 1:
                        likitide_durumu = f"{likitide_oranı} Likitide Çok Güçlü Borçları Anında kapıyabilir"
                    elif likitide_oranı > 0.80:
                        likitide_durumu = f"{likitide_oranı} Likitide Dengeli . Nakit Akışın Devamı gerekli"
                    elif likitide_oranı > 0.50:
                        likitide_durumu = f"{likitide_oranı} Likitide Zayıf Dikkatli Olunması Gerekli"
                    else:
                        likitide_durumu = f"{likitide_oranı} Likitide Krizi : Şirketin Nakit Durumu Çok Tehlikeli"
                else:
                    likite_durumu = f"Veri Alınamadı"
                peg_ratio = veri.info.get('trailingPegRatio')

                if peg_ratio:
                    if peg_ratio < 1:
                        peg_durum = f"{peg_ratio} Hisse Çok Ucuz (Kelepir)"
                    elif peg_ratio < 2:
                        peg_durum = f"{peg_ratio} Hisse Fiyatı Makul"
                    else:
                        peg_durum = f"{peg_ratio} Büyümesine Göre Pahalı"
                else:
                    peg_durum = f"Veri Alınamadı"

                alış = veri.info.get('ask')
                satış = veri.info.get('bid')
                if alış and satış:
                    if alış > satış * 2:
                        iştah = f"Alıcılar Çok Güçlü : Tahtada Alış Baskısı Var"
                    elif satış > alış * 2:
                        iştah = f"Satıcılar Çok Güçlü : Tahtada Satoş Baskısı Var"
                    else:
                        iştah = "Piyasa Dengeli : Alıcılar Ve Satıcılar Eşit Güçte"
                else:
                    iştah = "Veri Alınamadı"

                ma50 = veri.info.get('fiftyDayAverage')
                ma200 = veri.info.get('twoHundredDayAverage')
                if ma50 and ma200:
                    if ma50 > ma200:
                        ma_sinyal = "Golden Cross: Kısa Vadeli Trend Uzun Vadeyi Kırdı Boğa Piyasası Sinyali"
                    elif ma50 < ma200:
                        ma_sinyal = "Death Cross: Kısa Vadeli Trend Uzun Vadenin Altında Ayı Piyası Sinyali"
                    else:
                        ma_sinyal = "Nötr: Ortalamalar Birbirine Çok Yakın"
                else:
                    ma_sinyal = np.nan
                if not kuruluş_yılı:
                    kuruluş_yılı = "Belirtilmemiş"

                if not geçmiş_hepsi.empty:
                    ilk_gün = geçmiş_hepsi.iloc[0]
                    halka_arz = ilk_gün['Open']
                else:
                    geçmiş_hepsi = "Bulunmadı"
                if halka_arz_ms:
                    halka_arz_tarihi = datetime.fromtimestamp(halka_arz_ms / 1000.0).strftime('%d.%m.%Y')
                else:
                    halka_arz_tarihi = np.nan
                web_sitesi = veri.info.get('website')
                if not gelir or çalışan_sayısı or gelir_bölü_çalışan:
                    gelir = np.nan
                    çalışan_sayısı = np.nan
                    gelir_bölü_çalışan = np.nan

                cari_oran = veri.info.get("currentRatio")
                if not cari_oran:
                    cari_oran = np.nan
                if cari_oran >= 1.5:
                    cari_durum = f"{cari_oran} Güçlü : Şirket Kısa Vade Borçlarını Rahatça Ödeyebilir"
                elif cari_oran >= 1:
                    cari_durum = f"{cari_oran} Sınırda : Borç Ödeme Kapasitesi Yeterli Ama İzlenmeli"
                else:
                    cari_durum = f"{cari_oran} Riskli : Kısa Vadeli Borçlar Nakit Varlıklardan Fazla"

                if not kurumsal_yatırımcılar_sahiplik_oranı:
                    kurumsal_yatırımcılar_sahiplik_oranı = np.nan
                yüzde_sahiplik = kurumsal_yatırımcılar_sahiplik_oranı * 100
                if yüzde_sahiplik > 70:
                    sahiplik_durum = f"{yüzde_sahiplik} Yüksek :  Kurumsal Yatırımcılar Bu Hisseye Güveniyor"
                elif yüzde_sahiplik > 40:
                    sahiplik_durum = f"{yüzde_sahiplik} Orta : Kurumsal Ve Bireseysel Yatırımcı Oranı Dengeli"
                else:
                    sahiplik_durum = f"{yüzde_sahiplik} Düşük : Bireysel Yatırımcı Oranı Düşük"

                short_interest = veri.info.get('sharesShort', np.nan)
                if short_ratio > 3:
                    durum = f"Dikkat Açığa Satış Baskısı Var"
                elif short_ratio < 3:
                    durum = "Açığa Satış Oranı Düşük (Piyasa İyimser)"
                else:
                    durum = f"Açığa Satış Oranı Normal"

                if not borç_bölü_özkaynak_oran:
                    borç_bölü_özkaynak_oran = np.nan
                if not defter_değeri:
                    defter_değeri = np.nan
                net_kar_marjı = veri.info.get('profitMargins')
                if not net_kar_marjı:
                    net_kar_marjı = np.nan
                if öz_kaynak_karlılığı:
                    öz_kaynak_karlılığı = veri.info.get("returnOnEquity") * 100
                else:
                    öz_kaynak_karlılığı = np.nan
                hisse_başına_kar = veri.info.get('trailingEps')
                if not hisse_başına_kar:
                    hisse_başına_kar = np.nan
                FAVÖK = veri.info.get('enterpriseToEbitda')
                if not FAVÖK:
                    FAVÖK = np.nan
                hedef_fiyat = veri.info.get("targetMeanPrice")
                tavsiye = veri.info.get('recommendationKey')
                potansiyel = np.nan
                if hedef_fiyat is not None:
                    try:
                        hedef_fiyat = float(hedef_fiyat)
                    except:
                        hedef_fiyat = np.nan
                if hedef_fiyat:
                    potansiyel = ((hedef_fiyat - kapanıs) / kapanıs) * 100
                if not tavsiye or not hedef_fiyat:
                    hedef_fiyat = np.nan
                    tavsiye = np.nan
                en_yuksek

                skor = 0
                maks_skor = 100

                if cari_oran and cari_oran >= 1.5:
                    skor += 20
                elif cari_oran and cari_oran >= 1:
                    skor += 10

                if isinstance(likitide_oranı,(int,float)):
                    if likitide_oranı >= 1:
                        skor += 20
                    elif likitide_oranı >= 0.7:
                        skor += 10

                if öz_kaynak_karlılığı and öz_kaynak_karlılığı > 20:
                    skor += 20
                elif öz_kaynak_karlılığı and öz_kaynak_karlılığı > 10:
                    skor += 10

                if peg_ratio and peg_ratio < 1:
                    skor += 20
                elif peg_ratio and peg_ratio < 2:
                    skor += 10

                if ma50 and ma200 and ma50 > ma200:
                    skor += 20

                if skor >= 80:
                    güven_mesajı = f"🚀Çok Güçlü : Finansal Ve Teknik Göstergeler Mükemmel"
                    renk = "succes"  # HTML DE YEŞİL
                elif skor >= 50:
                    güven_mesajı = f"⚖️Dengeli : Şirket Sağlam Ama Bazı Riskler Barındırıyor"
                    renk = "warning"  # HTML DE SARI
                else:
                    güven_mesajı = f"⚠️Riskli : Göstergeler Zayıf Dikkatli Olunmalı"
                    renk = "danger"  # HTML DE KIRMIZI

                try:
                    insider_verisi = veri.get_insider_transactions()
                except:
                    insider_verisi = f"İnsider Verisi Çekilemedi"
                alımlar = insider_mesajı = "İçeriden Alım Bilgisi Yok"
                insider_renk = "text-dim"
                if insider_verisi is not None and isinstance(insider_verisi,pd.DataFrame) and not insider_verisi.empty:
                    alımlar = insider_verisi[insider_verisi['Transaction'] == "Buy"]
                    toplam_alınan_lot = alımlar['Shares'].sum() if not alımlar.empty else 0
                    if toplam_alınan_lot > 0:
                        insider_mesajı = (f"Olumlu : Yöneticiler Bu Şirkete Güveniyor")
                        insider_renk = "succes"
                        skor += 15
                    else:
                        insider_mesajı = "Son Dönemde Yönetici Seviyesinde Alım Saptanmadı"
                else:
                    inside_mesajı = "Kurumsal Sahiplik Oranı Bu Varlık İçin Geçerli Değil"

                zirveden_uzaklık = ((kapanıs - ATH) / ATH) * 100
                kapanıs_ath = veri_ath['Close'].max()


                fk_oran = None
                try:
                    gelir_tablosu = veri.financials
                    if not gelir_tablosu.empty and 'Net Income' in gelir_tablosu.index:
                        yıllık_net_kar = gelir_tablosu.loc['Net Income'].iloc[0]
                        if toplam_hisse_sayısı and yıllık_net_kar:
                            hbk = yıllık_net_kar / toplam_hisse_sayısı
                            fk_oran = kapanıs / hbk
                except:
                    fk_oran = None





            if df.empty:
                return "Hisse Girilmedi"


            KRİPTO_EVRENİ = ['BTC', 'ETH', 'BNB', 'SOL', 'XRP', 'ADA', 'DOGE', 'DOT', 'TRX', 'LINK', 'AVAX', 'MATIC',
                            'SHIB', 'TON', 'LTC', 'BCH', 'NEAR', 'UNI', 'ICP', 'APT', 'STX', 'FIL', 'ATOM', 'IMX',
                            'HBAR', 'ETC', 'KAS', 'OP', 'ARB', 'RNDR', 'VET', 'LDO', 'TIA', 'SUI', 'INJ', 'PEPE', 'FET',
                            'THETA', 'GRT', 'ALGO', 'SEI', 'FLOW', 'RUNE', 'GALA', 'AAVE', 'DYDX', 'SAND', 'MANA',
                            'CHZ', 'AXS', 'BEAM', 'PYTH', 'BONK', 'WIF', 'JUP', 'ORDI']

            temiz_sembol = sembol.split('-')[0].split('/')[0].strip().upper()
            kripto_mu = temiz_sembol in KRİPTO_EVRENİ

            if kripto_mu:
                arama_sembolü = f"{temiz_sembol}USDT"
                arbitraj_sonuc =  arbitraj_sonuc = {
                    "is_available": False,
                    "not": "Arbitraj Desteği Gelecek Sürümde Eklenecek"}
            else:
                arbitraj_sonuc = {
                    "is_available": False,
                    "not": "ℹ️ Bu varlık merkezi bir borsada (Hisse/Emtia) işlem görmektedir. Borsalar arası arbitraj sadece kripto varlıklar için desteklenmektedir."
                }

                ai_ozet_veri = {
                    "Hisse": long_name,
                    "Fiyat": f"{kapanıs} {sembol.split('=')[0]}",
                    "Skor": f"{skor}/100 ({güven_mesajı})",
                    "Cari Oran": cari_durum,
                    "ROE": f"%{öz_kaynak_karlılığı}",
                    "PEG": peg_durum,
                    "Teknik": ma_sinyal,
                    "Insider": insider_mesajı,
                    'Sektör': sektör,
                    "Hedef Potansiyel": f"%{potansiyel:.2f}" if potansiyel else "Yok",
                    "ATH Uzaklık": f"%{zirveden_uzaklık:.2f}",
                    "ADX_YÖN": adx_yön,
                    "ADX_TREND": adx_trend,
                    "ADX": güncel_adx,
                    "Dİ_PLUS": güncel_di_plus,
                    "di_minüs": güncel_di_minüs
                }
                ai_response = None

                emtia_isaretleri = ["=", "USD", "EUR", "TRY", "X", "GC", "SI", "PA", "PL"]

                if any(isaret in sembol for isaret in emtia_isaretleri):
                    ai_modu = "Emtia ve Döviz Piyasaları Uzmanı"
                    ek_talimat = (
                        "Bu bir emtia, parite veya değerli metaldir. Şirket bilançosu, hisse rasyosu gibi "
                        "kavramları kullanma. Küresel makroekonomik veriler, merkez bankası kararları ve "
                        f"arz-talep dengesi üzerinden profesyonel bir analiz yap. {ai_ozet_veri}"
                    )
                else:
                    ek_talimat = (
                        f"ÖNCELİKLE BU YORUMUN TAMAMINI {Dil} dilinde yap. "
                        f"Bu Hisse Verilerini Profesyonelce Kullanıcıya Verileri Tekrar Etmeden "
                        f"(Örneğin Peg Rasyosu 2 demene gerek yok) bu verilerden yola çıkarak "
                        f"hissenin ve şirketin geleceği potansiyel fırsatlar hakkında aşırı detaylı "
                        f"ve bunları çok detaylıca açıkladıktan sonra yazının en sonunda yorum yap. Ve Analaliz Aşırı Detaylı Olsun . Sondada Kullanıcıya AL SAT VEYA TUT de"
                        f"BU YORUMUN TAMAMINI {Dil} dilinde yap: {ai_ozet_veri}")

                try:
                    ai_response = client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=[
                            {
                                "role": "system",
                                "content": rol_tanımı
                            },
                            {
                                "role": "user",
                                "content": f"{ek_talimat}"
                            }
                        ],
                        max_tokens=2500,
                        temperature=0.7
                    )
                    ai_analiz_notu = ai_response.choices[0].message.content
                except Exception:
                    ai_response = None
                    ai_analiz_notu = f"⚠️ Analiz motorunda bir sorun oluştu:"




            return render_template("finanssonuc.html",
                                   ai_analiz_notu = ai_analiz_notu,arbitraj_sonuc=arbitraj_sonuc,
                                   hisse=sembol,
                                   fiyat=kapanıs_ath,
                                   tarih=tarih,
                                   kapanıs=kapanıs,
                                   en_yuksek=en_yuksek,
                                   en_dusuk=en_dusuk,
                                   hacim=hacim, ortalama_hacim=ortalama_hacim,fk=fk_oran,beta=beta,
                                   market_cap=market_cap,temettü=temettü,temettü_verim=temettü_verimi,
                                   ath=ATH,zirveden_uzaklık=zirveden_uzaklık,
                                   oz_kaynak_karlılığı = float(öz_kaynak_karlılığı),
                                   hedef_fiyat = hedef_fiyat,
                                   potansiyel = potansiyel,
                                   tavsiye = tavsiye,FAVÖK=FAVÖK,hisse_başına_kar=hisse_başına_kar,
                                   net_kar_marjı = net_kar_marjı,defter_değeri=defter_değeri,
                                   borç_bölü_özkaynak_oran = borç_bölü_özkaynak_oran,açığa_satış_durumu=durum,
                                   kurumsal_sahiplik = yüzde_sahiplik,sahiplik_durum=sahiplik_durum,
                                   cari_oran = cari_oran,cari_durum=cari_durum,
                                   halka_arz_tarihi = halka_arz_tarihi,
                                   adres = adres , web_site = web_sitesi,çalışan_sayısı=çalışan_sayısı,
                                   gelir_bölü_çalışan = gelir_bölü_çalışan,halka_arz_fiyatı=halka_arz,
                                   kuruluş_yılı=kuruluş_yılı,indikatör=iştah,renk=renk,güven_mesajı=güven_mesajı,peg_durum=peg_durum,insider_mesajı=insider_mesajı,öneriler=öneriler,
                                   ema_listesi = ema_listesi_tablo,ema_sözlük=ema_listesi_sözlük,long_name=long_name,bilanço_tarihi=bilanço_tarihi,bilanço_beklenti=bilanço_beklenti)

    except (requests.exceptions.ConnectionError, ConnectionError):
        return "<h1>🌐 Bağlantı Hatası</h1><p>İnternet bağlantınızı kontrol edin veya veri sağlayıcısının erişilebilir olduğundan emin olun.</p>"

    except ZeroDivisionError:
        return "<h1>🧮 Matematiksel Hata</h1><p>Veri setindeki eksiklikler nedeniyle finansal rasyolar hesaplanamadı (Sıfıra bölme hatası).</p>"

    except pd.errors.EmptyDataError:
        return "<h1>📉 Veri Boş</h1><p>Arattığınız hisse/kripto için geçmiş fiyat verisi bulunamadı.</p>"

    except ccxt.ExchangeError:
        return "<h1>🏛️ Borsa API Hatası</h1><p>Kripto borsasından veri çekilirken borsa kaynaklı bir hata oluştu.</p>"

    except ccxt.AuthenticationError:
        return "<h1>🔑 Yetkilendirme Hatası</h1><p>Borsa API anahtarlarınız hatalı veya süresi dolmuş.</p>"

    except PermissionError:
        return "<h1>🔒 Erişim Yetkisi Yok</h1><p>Sistem dosyalarına veya veritabanına erişim izniniz bulunmuyor.</p>"

    except Exception as e:
        return f"<h1>🛠️ Beklenmedik Bir Hata</h1><p>Sistem yöneticisine iletilmek üzere kaydedildi.</p>"
    finally:
        if veri is not None:
            del veri

        dataframe_list = [
            'gecmis_', 'df', 'ema_df', 'veri_ath', 'df_adx',
            'kar', 'max_geçmiş', 'geçmiş_hepsi', 'insider_verisi',
            'öneriler', 'ai_ozet_veri'
        ]

        for var_name in dataframe_list:
            if var_name in locals() and locals()[var_name] is not None:
                try:
                    del locals()[var_name]
                except:
                    pass
        list_list = [
            'ema_listesi_tablo', 'ema_listesi_sözlük', 'periyotlar',
            'haber_metni', 'son_haberler', 'alımlar'
        ]

        for var_name in list_list:
            if var_name in locals() and locals()[var_name] is not None:
                try:
                    del locals()[var_name]
                except:
                    pass

        if ai_response is not None:
            del ai_response
        gc.collect()
        gc.collect(generation=2)



@app.route("/Hacim_Ekranı")
def hacim_ekranı():
    try:
        p = session.get('last_period', '1mo')
        i = session.get('last_interval', '1d')
        s = session.get('last_sembol', '')
        return render_template("hacimmenu.html", p=p, i=i, s=s)
    except:
        return "<h1>Bir Hata Oluştu</h1>"


@app.route("/Hacim",methods=['POST'])
@cache.cached(timeout=300)
def hacim_bilgisi():
    try:
        period = request.form.get("period")
        interval = request.form.get("interval")
        sembol = request.form.get("hisse").strip().upper()
        session['last_period'] = period
        session['last_interval'] = interval
        session['last_sembol'] = sembol

        p = session.get('last_period', '1mo')
        i = session.get('last_interval', '1d')
        s = session.get('last_sembol', '')

        GEÇERLİ_PERIOD = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]
        GEÇERLİ_INTERVAL = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "1wk", "1mo"]
        if not sembol:
            return "Hisse Senedi Giriniz"
        if not period or not interval:
            period = "6mo"
            interval = "1d"

        try:
            df = yf.download(sembol, period=period, interval=interval,prepost=False)
        except:
            df = pd.DataFrame()

        df = df[df["Volume"] > 0].dropna()


        if df is None or df.empty:
            return "Veri Alınamadı"

        if not df.empty:
            if isinstance(df.columns,pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            ortalama_hacim = float(df["Volume"].mean())
            tp = (df['High'] + df['Low'] + df['Close']) / 3
            vwap = (tp * df['Volume']).cumsum() / df['Volume'].cumsum()

            son_vwap = float(vwap.iloc[-1])
            son_fiyat = float(df['Close'].iloc[-2])
            önceki_fiyat = float(df['Close'].iloc[-1])
            fiyat_değişim = ((son_fiyat - önceki_fiyat) / önceki_fiyat) * 100
            vwap_fark_yuzde = ((son_fiyat - son_vwap) / son_vwap) * 100
            son_hacim = float(df["Volume"].iloc[-1])
            en_yüksek_hacim = float(df["Volume"].max())
            high_volume_idx = df["Volume"].idxmax().strftime("%Y.%m.%d")
            en_düşük_hacim = float(df["Volume"].min())
            ortalama_hacim = float(df["Volume"].mean())
            min_volume_idx = df["Volume"].idxmin().strftime("%Y.%m.%d")
            hacim_std = float(df["Volume"].std())
            z_skor = (son_hacim - ortalama_hacim) / hacim_std
            tarih = df.index
            hacim = df["Volume"]
            ilk_hacim = float(hacim.iloc[0])
            hacim_durum = "Yüksek" if son_hacim > ortalama_hacim else "Düşük"
            if fiyat_değişim >= 0.5 and hacim_durum == "Yüksek":
                trend_mesaj = "Trend 0naylandı Sağlıklı Yükseliş"
                trend_detay = "Fiyat Yükselişi Yüksek Hacimle Destekleniyor"
                trend_renk = "succes"
                trend_ikon = "fa-check-circle"
            elif fiyat_değişim >= 0.5 and hacim_durum == "Düşük":
                trend_mesaj = "Zayıf Yükseliş : Boğa Tuzağı Olabilir"
                trend_detay = "Fiyat Yükseliyor Ama Hacim Desteği"
                trend_renk = "warning"
                trend_ikon = "fa-exclamation-triangle"
            elif fiyat_değişim <= 0.5 and hacim_durum == "Yüksek":
                trend_mesaj = "Güçlü Satış Baskısı Ayı OLabilir"
                trend_detay = "Fiyat Yüksek Hacimle Düşüyor . Kurumsal Veya Panik Satışı Hakim"
                trend_renk = "danger"
                trend_ikon = "fa-arrow-down"
            elif fiyat_değişim <=0.5 and hacim_durum == "Düşük":
                trend_mesaj = "Kararsız Geri Çekilme"
                trend_detay = "Fiyat Düşüyor Ama Hacim Çok Zayıf Ciddi Trend Değişimi Yok"
                trend_renk = "info"
                trend_ikon = "fa-pause-circle"
            else:
                trend_mesaj = "Yatay Bant"
                trend_detay = "Fiyat Ve Hacim Dengede Piyasa Yeni Bir Yöntem Tayin Ediyor"
                trend_renk = "info"

            hacim_fark_yüzde = ((son_hacim - ilk_hacim) / ilk_hacim) * 100
            x_ekseni = df.index.strftime('%H:%M' if "m" in interval else '%d.%m.%y').tolist()
            y_ekseni = np.array(df['Volume'].values).flatten().tolist()
            if son_hacim > ortalama_hacim + hacim_std:
                renk = "red"
            elif son_hacim < ortalama_hacim - hacim_std:
                renk = "red"
            else:
                renk = "green"

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=x_ekseni,y=y_ekseni,fill='tozeroy',mode='lines',line=dict(color='#00ffbb', width=2),fillcolor='rgba(0, 255, 187, 0.1)',name='Hacim',hovertemplate='<b>Tarih:</b> %{x}<br><b>Hacim:</b> %{y:,.0f}<extra></extra>'))
            fig.add_hline(y=ortalama_hacim,line_color='gray',opacity=0.3,line_dash='dash')
            fig.update_layout(
                template='plotly_dark',
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis=dict(showgrid=False, color='#64748b'),
                yaxis=dict(showgrid=True, gridcolor='#1e293b', color='#64748b'),
                hovermode='x unified',
                hoverlabel=dict(
                    bgcolor="#020617",
                    bordercolor="#1e293b",
                    font_color="#e2e8f0",
                    font_family="Fira Code"
                )
            )
            hacim_json = json.dumps(fig,cls=PlotlyJSONEncoder)


            return render_template("hacimsonuc.html",ortalama_hacim=ortalama_hacim,
                       son_hacim=son_hacim,
                       en_yüksek_hacim=en_yüksek_hacim,
                       high_volume_idx=high_volume_idx,
                       son_vwap=son_vwap,
                       vwap_fark=round(vwap_fark_yuzde, 2),
                       vwap_fark_yuzde=vwap_fark_yuzde,
                       en_düşük_hacim=en_düşük_hacim,
                       min_volume_idx=min_volume_idx,
                       z_skor=z_skor,
                       renk=renk,ilk_tarih=df.index[0].strftime("%Y-%m-%d"),
                       son_tarih=df.index[-1].strftime("%Y-%m-%d"),hacim_json=hacim_json,hacim_fark_yüzde=round(hacim_fark_yüzde),ilk_hacim=ilk_hacim,
                       trend_renk=trend_renk,trend_ikon=trend_ikon,trend_mesaj=trend_mesaj,fiyat_değişim=fiyat_değişim)
    except KeyError as e:
        return f"<h1>📊 Veri Formatı Hatası</h1><p>Borsadan gelen verilerde beklenen ... alanı bulunamadı.</p>"
    except requests.exceptions.Timeout:
        return "<h1>⌛ Sunucu Yanıt Vermiyor</h1><p>Veri kaynağı (Yahoo Finance/Borsa) çok geç yanıt veriyor, lütfen tekrar deneyin.</p>"


    except (requests.exceptions.ConnectionError, ConnectionError):
        return "<h1>🌐 Bağlantı Hatası</h1><p>İnternet bağlantınızı kontrol edin veya veri sağlayıcısının erişilebilir olduğundan emin olun.</p>"

    except ZeroDivisionError:
        return "<h1>🧮 Matematiksel Hata</h1><p>Veri setindeki eksiklikler nedeniyle finansal rasyolar hesaplanamadı (Sıfıra bölme hatası).</p>"

    except pd.errors.EmptyDataError:
        return "<h1>📉 Veri Boş</h1><p>Arattığınız hisse/kripto için geçmiş fiyat verisi bulunamadı.</p>"

    except ccxt.ExchangeError:
        return "<h1>🏛️ Borsa API Hatası</h1><p>Kripto borsasından veri çekilirken borsa kaynaklı bir hata oluştu.</p>"

    except ccxt.AuthenticationError:
        return "<h1>🔑 Yetkilendirme Hatası</h1><p>Borsa API anahtarlarınız hatalı veya süresi dolmuş.</p>"

    except PermissionError:
        return "<h1>🔒 Erişim Yetkisi Yok</h1><p>Sistem dosyalarına veya veritabanına erişim izniniz bulunmuyor.</p>"

    except Exception as e:
        return f"<h1>🛠️ Beklenmedik Bir Hata</h1><p>Sistem yöneticisine iletilmek üzere kaydedildi.</p>"
    finally:
        if hacim_json:
            del hacim_json
        gc.collect()

def val_ex(x):
    try:
        if x is not None and x != "Bilinmiyor" and x != "Hesaplanamadı" and x != "Veri Yetersiz" and x != "Aktif Değil":
            return x
    except:
        pass
    return "Bilinmiyor"
@app.route("/Grafikler")
@cache.cached(timeout=300)
def grafikler():
    p = session.get('last_period', '1mo')
    i = session.get('last_interval', '1d')
    s = session.get('last_sembol', '')
    d = session.get('last_language', 'Türkçe')

    return render_template(
        "grafik.html",
        saved_p=p,
        saved_i=i,
        saved_s=s,
        saved_d=d
    )




def _find_col(columns, *candidates):
    for c in columns:
        s = str(c)
        for cand in candidates:
            if cand in s:
                return c
    return None


def knoxville_divergence(df, osc_col):
    try:
        if df is None or df.empty or osc_col not in df.columns:
            return df

        close_ser = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
        low_ser = df['Low'].iloc[:, 0] if isinstance(df['Low'], pd.DataFrame) else df['Low']
        high_ser = df['High'].iloc[:, 0] if isinstance(df['High'], pd.DataFrame) else df['High']
        osc_ser = df[osc_col].iloc[:, 0] if isinstance(df[osc_col], pd.DataFrame) else df[osc_col]

        diff_period = 20 if len(df) > 30 else 5

        df = df.copy()
        df['mom_20'] = close_ser.diff(diff_period)

        df['knox_bull'] = (low_ser < low_ser.shift(1)) & (osc_ser > osc_ser.shift(1))

        df['knox_bear'] = (high_ser > high_ser.shift(1)) & (osc_ser < osc_ser.shift(1))

        return df
    except:
        return f"Bir Hata Oluştu "


def safe_append_indicator(df, indicator_data, fallback_name):
    try:
        if indicator_data is None:
            return df

        try:
            if isinstance(indicator_data, pd.Series):
                indicator_data.name = fallback_name if not indicator_data.name else indicator_data.name
                return pd.concat([df, indicator_data], axis=1)
            elif isinstance(indicator_data, pd.DataFrame):
                return pd.concat([df, indicator_data], axis=1)

        except Exception as e:
            print(f"Hata: {fallback_name} eklenirken bir problem oluştu: {e}")

        return df
    except:
        return f"Bir Hata Oluştu"

@app.route("/Grafik Penceresi", methods=["POST"])
def grafik_penceresi():
    try:
        def flat_cols(d):
            if isinstance(d.columns, pd.MultiIndex):
                d = d.copy()
                d.columns = d.columns.get_level_values(0)
            return d

        def find_col(columns, *candidates):
            for c in columns:
                s = str(c)
                for cand in candidates:
                    if cand in s:
                        return c
            return None

        sembol = request.form.get("hisse", "").strip()
        interval = request.form.get("interval", "1d")
        period = request.form.get("period", "1mo")
        dil = request.form.get("dil", "Türkçe")

        session["last_period"] = period
        session["last_interval"] = interval
        session["last_sembol"] = sembol
        session["last_language"] = dil

        if zaman_dilimi_kontrol(interval, period):
            return "<h1>Hata: Mum Aralığı (Interval), toplam periyottan büyük veya eşit olamaz!</h1>"


        if not sembol:
            return "Hisse boş"

        df = yf.download(
            sembol, period=period, interval=interval, progress=False,
            auto_adjust=True, actions=True, threads=False,prepost=False
        )
        if df.empty or len(df) < 2:
            return "Hisse Senedi Bulunamadı veya yetersiz veri"

        df = pd.DataFrame(df)
        df = flat_cols(df)
        if "Adj Close" in df.columns:
            df = df.drop(columns=["Adj Close"])
        df = df.dropna(how="all")

        ichi_sonuc = df.ta.ichimoku()
        if ichi_sonuc is not None and isinstance(ichi_sonuc, tuple) and len(ichi_sonuc) > 0:
            try:
                ichi_df = flat_cols(ichi_sonuc[0].copy())
                df = pd.concat([df, ichi_df], axis=1)
            except:
                pass
        else:
            pass

        df.ta.adx(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.alma(length=9, offset=0.85, sigma=6, append=True)
        df.ta.adosc(fast=3, slow=10, append=True)
        try:
            wma_res = df.ta.wma(length=9)
            if wma_res is not None:
                if isinstance(wma_res, pd.Series):
                    wma_res.name = "WMA_9"
                df = pd.concat([df, wma_res], axis=1)

                wma_col = find_col(df.columns, "WMA_9")
        except:
            pass

        df = flat_cols(df)
        df.dropna(subset=['Close', 'Open', 'High', 'Low'], inplace=True)
        if len(df) < 2:
            pass
        cmo_col = smi_col = smi_sig_col = psar_l_col = psar_s_col = None
        ui_col = ui_df = tsi_col = tsi_sig_col = nvi_col = nvi_sig_col = None
        spk_col = pmo_col = rvi_col = rvi_sig_col = uo_col = None

        date_fmt = "%H:%M" if "m" in str(interval).lower() else "%d.%m.%y"
        x_ekseni = df.index.strftime(date_fmt).tolist()
        n = len(df)

        mum_open = df["Open"].values.flatten().tolist()
        mum_high = df["High"].values.flatten().tolist()
        mum_low = df["Low"].values.flatten().tolist()
        mum_close = df["Close"].values.flatten().tolist()
        volume_values = df["Volume"].values.flatten().tolist()

        hacim_etiketleri = [
            f"Volume: {int(v):,}<br>Range: {(h - l):.2f}<br>Change: %{((c / o) - 1) * 100:.2f}"
            for v, h, l, o, c in zip(
                volume_values,
                mum_high,
                mum_low,
                mum_open,
                mum_close,
            )
        ]

        adx_col = find_col(df.columns, "ADX")
        bbu_col = find_col(df.columns, "BBU")
        bbm_col = find_col(df.columns, "BBM")
        bbl_col = find_col(df.columns, "BBL")
        alma_col = find_col(df.columns, "ALMA")
        adosc_col = find_col(df.columns, "ADOSC")
        wma_col = find_col(df.columns, "WMA")
        isa_col = find_col(df.columns, "ISA_9", "ISA")
        isb_col = find_col(df.columns, "ISB_26", "ISB")
        try:
            lrc_res = df.ta.linreg(length=20)
            if lrc_res is not None:
                df['LRC_20'] = lrc_res
                lrc_col = 'LRC_20'
        except:
            lrc_col = None

        son_fiyat = float(mum_close[-1])
        ilk_fiyat = float(mum_close[0])
        veri_ath = yf.download(sembol, period="max", interval="1d", progress=False, auto_adjust=True,prepost=False)
        veri_ath = flat_cols(pd.DataFrame(veri_ath))
        ath = float(veri_ath["Close"].max())
        atl = float(veri_ath["Close"].min())
        zirveden_uzaklık = ((ath - son_fiyat) / ath * 100) if ath else 0
        last_adx = float(df[adx_col].iloc[-1]) if adx_col else 0
        last_alma = float(df[alma_col].iloc[-1]) if alma_col else 0
        last_cho = float(df[adosc_col].iloc[-1]) if adosc_col else 0
        bb_upper = float(df[bbu_col].iloc[-1]) if bbu_col else 0
        bb_middle = float(df[bbm_col].iloc[-1]) if bbm_col else 0
        bb_lower = float(df[bbl_col].iloc[-1]) if bbl_col else 0
        try:
            df['BEAR_5'] = ((df['High'] > df['High'].shift(1)) &
                            (df['High'] > df['High'].shift(2)) &
                            (df['High'] > df['High'].shift(-1)) &
                            (df['High'] > df['High'].shift(-2)))

            df['BULL_5'] = ((df['Low'] < df['Low'].shift(1)) &
                            (df['Low'] < df['Low'].shift(2)) &
                            (df['Low'] < df['Low'].shift(-1)) &
                            (df['Low'] < df['Low'].shift(-2)))
        except:
            pass

        bull_col = _find_col(df.columns, "BULL_5")
        bear_col = _find_col(df.columns, "BEAR_5")
        atr = df.ta.atr(length=10)
        high_stop = df['High'].rolling(window=10).max() - 1 * atr
        low_stop = df['Low'].rolling(window=10).min() + 1 * atr

        hv_col = None
        try:
            hv_raw = df.ta.hv(length=30)
            if hv_raw is not None:
                hv_raw = hv_raw * 100  # 0.02 -> 2.0 olur
                hv_df = hv_raw.to_frame() if isinstance(hv_raw, pd.Series) else hv_raw


                hv_col = "HV_Vol"
                hv_df.columns = [hv_col]
                hv_df.index = df.index

                hv_df[hv_col] = hv_df[hv_col].fillna(0).replace([np.inf, -np.inf], 0).round(4)

                df = pd.concat([df, hv_df], axis=1)
                print(f"DEBUG: HV başarıyla eklendi, son değer: {df[hv_col].iloc[-1]}")
        except Exception as e:
            print(f"HV Hatası: {e}")
        try:
            if low_stop is not None:
                low_stop_array = np.array(low_stop)
                low_stop_series = pd.Series(low_stop_array)
                df['CKS_long'] = low_stop_series.rolling(window=9, min_periods=1).min()
            else:
                df['CKS_long'] = np.nan
        except:
            df['CKS_long'] = np.nan
        df['CKS_Short'] = low_stop.rolling(window=9).max()
        cks_l_col = _find_col(df.columns, "CKS_Long")
        cks_s_col = _find_col(df.columns, "CKS_Short")
        trix_col = None
        trix_sig_col = None

        try:
            cexit = df.ta.ced(length=22, multiplier=3)

            if cexit is not None:
                df['Chandelier_Long'] = cexit.iloc[:, 0]
                df['Chandelier_Short'] = cexit.iloc[:, 1]
                ce_ready = True
            else:
                ce_ready = False
        except:
            ce_ready = False

        try:
            trix_len = 9 if len(df) < 30 else 12
            trix_res = df.ta.trix(length=trix_len, signal=9, scalar=100)

            if trix_res is not None:
                trix_res = trix_res.to_frame() if isinstance(trix_res, pd.Series) else trix_res
                trix_res = flat_cols(trix_res)

                # Sütun isimlerini değişkene ata
                trix_col = trix_res.columns[0]
                if len(trix_res.columns) > 1:
                    trix_sig_col = trix_res.columns[1]

                # Ana tabloya (df) ekle ki çizim kısmında bulabilsin
                df = pd.concat([df, trix_res], axis=1)
        except Exception as e:
            pass
        if len(df) >= 14:
            try:
                cmo_res = df.ta.cmo(length=14)
                if cmo_res is not None:
                    if isinstance(cmo_res, pd.Series):
                        df['CMO'] = cmo_res
                    else:
                        df = pd.concat([df, cmo_res], axis=1)
            except Exception as e:
                print(f"CMO Hesaplanırken hata: {e}")
        smi_df_data = df.ta.smi(lenght=13, scalar=100, signal=25)
        smi_col = _find_col(smi_df_data.columns, "SMI_13_25_2")
        smi_sig_col = _find_col(smi_df_data.columns, "SMIs_13_25_2")
        psar_df = df.ta.psar(af=0.02, max_af=0.02)
        psar_l_col = _find_col(psar_df.columns, "PSARl")
        psar_s_col = _find_col(psar_df.columns, "PSARs")
        df = safe_append_indicator(df, df.ta.kama(length=10), "KAMA")

        try:
            ui_res = df.ta.ui(length=14)
            df['UI_14'] = ui_res
            ui_col = 'UI_14'
            df = pd.concat(df[df,ui_res],axis=1)
        except:
            ui_col = None

        ema_lengths = [5, 10, 20, 30, 50, 100, 150, 200]

        try:
            kst_res = df.ta.kst(sma1=10, sma2=10, sma3=10, sma4=15, roc1=10, roc2=15, roc3=20, roc4=30, signal=9)
            if kst_res is not None:
                kst_res = flat_cols(kst_res)
                df = pd.concat([df, kst_res], axis=1)
                kst_col = _find_col(df.columns, "KST_")
                kst_sig_col = _find_col(df.columns, "KSTs_")
        except:
            kst_col = None
            kst_sig_col = None

        for length in ema_lengths:
            try:
                ema_result = df.ta.ema(length=length)
                if ema_result is not None:
                    if isinstance(ema_result, pd.Series):
                        ema_result = ema_result.to_frame()
                        df[f'EMA_{length}'] = ema_result.iloc[-1]
                    else:
                        df[f'EMA_{length}'] = ema_result
            except:
                ema_result = None
        kama_col = _find_col(df.columns, "KAMA")
        rvi_df = df.ta.rvi(length=14, swma=4)

        tsi_col = "TSI_13_25_13"
        tsi_sig_col = "TSIs_13_25_13"
        tsi_df = None
        try:
            tsi_res = df.ta.tsi(fast=13, slow=25, signal=13)
            if isinstance(tsi_res, (pd.DataFrame, pd.Series)):
                tsi_res = float(tsi_res.iloc[0])
            if isinstance(tsi_res.columns, pd.DataFrame):
                tsi_res.columns = tsi_res.columns
                if len(tsi_df.columns) >= 2:
                    tsi_df.columns = [tsi_col, tsi_sig_col]

        except Exception:
            print('Hata Veri Hesaplanamadı')
        df.ta.vortex(legnth=14)
        rvi_raw = df.ta.rvi(length=14, signal=4)
        rvi_df = rvi_raw.to_frame() if isinstance(rvi_raw, pd.Series) else rvi_raw
        rvi_col = rvi_df.columns[0]

        # 2. Sütun (eğer varsa) Sinyal hattıdır
        if len(rvi_df.columns) > 1:
            rvi_sig_col = rvi_df.columns[1]
        else:
            rvi_sig_col = None

        # Ana df ile birleştirmeyi unutma ki grafik çizerken bulabilsin
        df = pd.concat([df, rvi_df], axis=1)

        # Sütun ismini manuel aramak yerine rvi_df içindeki İLK sütunu al (çünkü zaten RVI verisi)
        if rvi_df is not None and not rvi_df.empty:
            rvi_sig_col = rvi_df.columns[0]  # Hangi isimle oluşursa oluşsun ilk sütunu seçer
        else:
            rvi_sig_col = None

        nvi = np.nan
        desenler = []
        try:
            c_son = float(df['Close'].iloc[-1])
            o_son = float(df['Open'].iloc[-1])
            l_son = float(df['Low'].iloc[-1])

            c_prev = float(df['Close'].iloc[-2])
            o_prev = float(df['Open'].iloc[-2])

            if c_son > o_son and (o_son - l_son) > 2 * (c_son - o_son):
                desenler.append("Çekiç (Boğa Sinyali)")

            # 2. Yutan Boğa Kontrolü
            if c_son > o_son and c_prev < o_prev:
                if c_son > o_prev and o_son < c_prev:
                    desenler.append("Yutan Boğa (Güçlü Alış)")

        except Exception as e:
            print(f"Desen analizi sırasında hata (Muhtemelen yetersiz veri): {e}")

        try:
            uo_res = df.ta.uo(fast=7, medium=14, slow=28)
            if uo_res is not None:
                df['UO'] = uo_res
                uo_col = 'UO'
                df = pd.concat([df,uo_res],axis=1)
                print(">>> Ultimate Oscillator başarıyla hesaplandı.")
            else:
                uo_col = None
        except Exception as e:
            uo_col = None
            print(f">>> UO Hatası: {e}")
        tsi_df = None
        tsi_col = None
        tsi_sig_col = None

        try:
            tsi_res = df.ta.tsi(fast=13, slow=25, signal=13)
            if tsi_res is not None:
                if isinstance(tsi_res, pd.Series):
                    tsi_res = tsi_res.to_frame()

                tsi_res = flat_cols(tsi_res)

                if len(tsi_res.columns) >= 1:
                    tsi_col = tsi_res.columns[0]
                    if len(tsi_res.columns) >= 2:
                        tsi_sig_col = tsi_res.columns[1]
                    else:
                        tsi_sig_col = f"{tsi_col}_Signal"
                        tsi_res[tsi_sig_col] = tsi_res[tsi_col].ewm(span=13, adjust=False).mean()
                    df = pd.concat([df, tsi_res], axis=1)
                    tsi_df = tsi_res
        except Exception as e:
            print(f"TSI hesaplama hatası: {e}")
            tsi_df = None
            tsi_col = None
            tsi_sig_col = None

        ui_col = 'UI_14'
        ui_df = None
        try:
            ui_res = df.ta.ui(length=14)
            if ui_res is not None:
                df = pd.concat([df, ui_res], axis=1)
                ui_col = find_col(df.columns, "UI")
        except Exception as e:
            print(f"Ulcer Index hatası: {e}")
            ui_col = None
        try:
            nvi_series = df.ta.nvi()
            if isinstance(nvi_series, pd.Series):
                nvi_df = nvi_series.to_frame()
            if nvi_series is not None:
                df['NVI'] = nvi_series
                df['NVI_Signal'] = df["NVI"].ewm(span=255, adjust=False).mean()
                nvi_col = 'NVI'
                nvi_sig_col = 'NVI_Signal'
        except Exception as e:
            print(f"NVI Hatası: {e}")
            nvi_col, nvi_sig_col = None, None

        try:
            rsi_res = df.ta.rsi(length=14)
            if rsi_res is not None:
                df['RSI_14'] = rsi_res
                rsi_col = 'RSI_14'
                print(">>> RSI başarıyla hesaplandı.")
            else:
                rsi_col = None
        except:
            rsi_col = None

        try:
            trix_res = df.ta.trix(length=15)
            if trix_res is not None:
                df['TRIX'] = trix_res.iloc[:, 0]
                df['TRIX_Sig'] = trix_res.iloc[:, 1]
                trix_col = 'TRIX'
                trix_sig_col = 'TRIX_Sig'
                print(">>> TRIX başarıyla hesaplandı.")
            else:
                trix_col = None
        except Exception as e:
            trix_col = None
            print(f">>> TRIX Hatası: {e}")

        if uo_res is not None:
            try:
                df = pd.concat([df, uo_res], axis=1)
                uo_col = find_col(df.columns, "UO")
            except Exception as e:
                print(f"UO eklenirken hata oluştu: {e}")
                uo_col = None
        if son_fiyat >= ilk_fiyat:
            ana_renk = "#00ffbb"
            dolgu_renk = "rgba(0, 255, 187, 0.2)"
        else:
            ana_renk = "#ff4b5c"
            dolgu_renk = "rgba(255, 75, 92, 0.2)"
        uo_col = find_col(df.columns, "UO")
        pmo_col = None
        pmo_sig_col = None
        try:
            dpo_res = df.ta.dpo(length=20)
            if dpo_res is not None:

                if isinstance(dpo_res, pd.Series):
                    dpo_res.name = "DPO_20"
                df = pd.concat([df, dpo_res], axis=1)
                dpo_col = "DPO_20"
            else:
                dpo_col = None
        except Exception as e:
            print(f"DPO Hesaplama Hatası: {e}")
            dpo_col = None
        try:
            ema12_vol = df['Volume'].ewm(span=12, adjust=False).mean()
            ema26_vol = df['Volume'].ewm(span=26, adjust=False).mean()

            df['PVO_Manuel'] = ((ema12_vol - ema26_vol) / ema26_vol) * 100
            df['PVO_Signal_Manuel'] = df['PVO_Manuel'].ewm(span=9, adjust=False).mean()
            df['PVO_Hist_Manuel'] = df['PVO_Manuel'] - df['PVO_Signal_Manuel']

            # 2. Hesaplama başarılıysa isimleri ata
            pmo_col = "PVO_Manuel"
            pmo_sig_col = "PVO_Signal_Manuel"

        except Exception:
            pass
        spk_df = np.nan
        spk_col = np.nan
        try:
            if len(df) >= 700:
                spk_df = df.ta.specialk(append=False)
                spk_col = _find_col(spk_df.columns, "SPK")
            else:
                spk_df = np.nan
                print(f"Special K Atlama: Veri yetersiz veya hesaplanamadı.")
                pass
        except:
            spk_col = np.nan
            print(f"Special K Atlama: Veri yetersiz veya hesaplanamadı.")
            pass

        if bbu_col and bbm_col and bbl_col:
            if son_fiyat >= bb_upper:
                bb_notu = "Fiyat Üst Bantta – Aşırı Alım veya güçlü yükseliş trendi."
            elif son_fiyat <= bb_lower:
                bb_notu = "Fiyat Alt Bantta – Aşırı Satım veya güçlü düşüş trendi."
            else:
                bb_notu = "Fiyat orta bant civarında – Dengeli bölge."
            bw = (bb_upper - bb_lower) / bb_middle if bb_middle else 0
            if bw < 0.1:
                bb_notu += " Bollinger bantlarında ciddi sıkışma – Kırılım görülebilir."
        else:
            bb_notu = "Bollinger verisi alınamadı."

        if son_fiyat > last_alma:
            alma_notu = "Fiyat ALMA (9) üzerinde – Kısa vadeli ivme pozitif."
        elif son_fiyat < last_alma:
            alma_notu = "Fiyat ALMA (9) altında – Kısa vadeli baskı olabilir."
        else:
            alma_notu = "Fiyat ALMA (9) ile bitişik – Karar aşaması."

        cho_notu = "Pozitif (Para girişi)" if last_cho > 0 else "Negatif (Para çıkışı)"
        donchian_df = df.ta.donchian(lower_length=20, upper_length=20)

        if isinstance(donchian_df, pd.MultiIndex):
            donchian_df.columns = donchian_df.columns.get_level_values(0)
        if donchian_df is not None:
            df = pd.concat([df, donchian_df], axis=1)

        dcl_col = find_col(df.columns, "DCL")
        dcm_col = find_col(df.columns, "DCM")
        dcu_col = find_col(df.columns, "DCU")

        analiz_maddeleri = []
        if isa_col and isb_col:
            raw_a = df[isa_col].iloc[-1]
            raw_b = df[isb_col].iloc[-1]
            if isinstance(raw_a, (pd.DataFrame, pd.Series)):
                son_span_a = df[isa_col].iloc[-1]
            else:
                son_span_a = raw_a
            if isinstance(raw_b, (pd.DataFrame, pd.Series)):
                son_span_b = df[isb_col].iloc[-1]
            else:
                son_span_b = float(raw_b)
            s_a = float(raw_a.iloc[0]) if hasattr(raw_a, 'iloc') else float(raw_a)
            s_b = float(raw_b.iloc[0]) if hasattr(raw_b, 'iloc') else float(raw_b)
            if son_fiyat > max(s_a, s_b):
                analiz_maddeleri.append("Fiyat Ichimoku bulutunun üzerinde – teknik görünüm güçlü.")
            elif son_fiyat < min(s_a, s_b):
                analiz_maddeleri.append("Fiyat bulutun altında – ayı baskısı.")
            else:
                analiz_maddeleri.append("Fiyat bulut içinde – kararsız bölge.")
        if last_adx > 25:
            analiz_maddeleri.append(f"Trend gücü (ADX: {round(last_adx, 1)}): Hareket kararlı.")
        else:
            analiz_maddeleri.append(f"Trend gücü (ADX: {round(last_adx, 1)}): Belirgin yön yok.")

        # ——— 4. EK GRAFİKLER (line, bar, hacimli mum) ———
        max_vol = max(volume_values) if volume_values else 1
        mum_genislikleri = [0.2 + (v / max_vol) * 0.6 for v in volume_values]
        hacim_etiketleri_kisa = [f"Hacim: {int(v):,}" for v in volume_values]

        try:
            st_df = df.ta.supertrend(period=7, multiplier=3)
            if st_df is not None:
                st_df = flat_cols(st_df)
                df = pd.concat([df, st_df], axis=1)
                st_col = _find_col(df.columns, "SUPERT_")
                st_dir_col = _find_col(df.columns, "SUPERTd_")
        except:
            st_col = None
            st_dir_col = None

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x_ekseni, y=mum_close, mode="lines",
                line=dict(color="#00ffbb", width=2), name="Kapanış"
            )
        )
        fig.update_layout(
            template="plotly_dark",
            height=400,
            title=dict(
                text="Kapanış Fiyatı (Hızlı Analiz)",
                x=0.5,
                font=dict(color="#3b82f6", size=16)
            ),
            hovermode="x unified",
            hoverlabel=dict(
                bgcolor="#0f172a",
                font_size=13,
                font_family="Fira Code",
                font_color="#f8fafc"
            ),
            xaxis=dict(
                type="category",
                showspikes=True,
                spikemode="across",
                spikethickness=1,
                spikedash="dash",
                spikecolor="#94a3b8",
                gridcolor="rgba(255,255,255,0.05)"
            ),
            yaxis=dict(
                side="right",
                gridcolor="rgba(255,255,255,0.05)",
                fixedrange=False
            ),
            paper_bgcolor="#020617",
            plot_bgcolor="#020617",
            margin=dict(l=20, r=20, t=60, b=20)
        )
        fig_line = json.dumps(fig,cls=PlotlyJSONEncoder)

        fig_candle_volume = go.Figure()
        for i in range(n):
            renk = "#00ffbb" if mum_close[i] >= mum_open[i] else "#ff4b5c"
            fig_candle_volume.add_trace(
                go.Scatter(
                    x=[x_ekseni[i], x_ekseni[i]], y=[mum_low[i], mum_high[i]],
                    mode="lines", line=dict(color=renk, width=1), showlegend=False
                )
            )
            fig_candle_volume.add_trace(
                go.Bar(
                    x=[x_ekseni[i]], y=[abs(mum_close[i] - mum_open[i])],
                    base=[min(mum_open[i], mum_close[i])], width=[mum_genislikleri[i]],
                    marker_color=renk, showlegend=False, hovertext=hacim_etiketleri[i], hoverinfo="text"
                )
            )

            df['SMA50'] = df.ta.sma(length=50)
            df['SMA200'] = df.ta.sma(length=200)

            gold_cross = (df['SMA50'] > df['SMA200']) & (df['SMA50'].shift(1) <= df['SMA200'].shift(1))
            death_cross = (df['SMA50'] < df['SMA200']) & (df['SMA50'].shift(1) >= df['SMA200'].shift(1))


            fig_candle_volume.update_layout(
                template="plotly_dark",
                height=500,
                title=dict(
                    text="Hacimli Mum Analizi (Overlay)",
                    x=0.5,
                    font=dict(color="#00ffbb", size=16)
                ),
                hovermode="x unified",
                hoverlabel=dict(
                    bgcolor="#0f172a",
                    font_size=13,
                    font_family="Fira Code"
                ),
                xaxis=dict(
                    type="category",
                    showspikes=True,
                    spikemode="across",
                    spikethickness=1,
                    spikedash="dot",
                    spikecolor="#94a3b8"
                ),
                yaxis=dict(
                    side="right",
                    gridcolor="rgba(255,255,255,0.05)"
                ),
                barmode="overlay",
                paper_bgcolor="#020617",
                plot_bgcolor="#020617",
                margin=dict(l=20, r=20, t=60, b=20),
                showlegend=True )
        fig_candle_volume_json = json.dumps(fig_candle_volume, cls=PlotlyJSONEncoder)
        del fig_candle_volume

        try:
            aroon_res = df.ta.aroon(length=25)
            aroon_up_col, aroon_down_col, aroon_osc_col = None, None, None

            if aroon_res is not None:
                df = pd.concat([df, aroon_res], axis=1)
                aroon_up_col = aroon_res.columns[0]
                aroon_down_col = aroon_res.columns[1]
                aroon_osc_col = aroon_res.columns[2]
        except:
            print('HATA')

        renkler = ["#00ffbb" if mum_close[i] >= mum_open[i] else "#ff4b5c" for i in range(n)]
        fig_bar = go.Figure()
        fig_bar.add_trace(
            go.Bar(x=x_ekseni, y=mum_close, marker=dict(color=renkler), name="Fiyat")
        )
        fig_bar.update_layout(
            template="plotly_dark",
            height=400,
            title=dict(text="Zaman-Fiyat (Sütun)", x=0.5, font=dict(color="#00ffbb")),
            hovermode="x unified",
            hoverlabel=dict(bgcolor="#0f172a", font_size=13),
            xaxis=dict(
                type="category",
                showspikes=True,
                spikecolor="#94a3b8"
            ),
            paper_bgcolor="#020617",
            plot_bgcolor="#020617",
        )
        bar_json = json.dumps(fig_bar,cls=PlotlyJSONEncoder)
        del fig_bar

        try:
            basis = df.ta.sma(length=20)
            basis = basis.to_frame() if isinstance(basis, pd.Series) else basis
            df['Zarf_Ust'] = basis * (1 + 0.025)
            df['Zarf_Alt'] = basis * (1 - 0.025)
        except Exception as e:
            print(f"Zarf hesaplama hatası: {e}")

        hollow_candle = go.Figure()
        hollow_candle.add_trace(
            go.Candlestick(x=x_ekseni,
                           open=mum_open,
                           close=mum_close,
                           low=mum_low,
                           high=mum_high,
                           increasing_line_color="rgba(0, 255, 187, 0.6)",
                           increasing_fillcolor="#020617",
                           decreasing_line_color="#ff4b5c",
                           decreasing_fillcolor="#ff4b5c",
                           name="Hollow Candle"))

        hollow_candle.update_layout(
            plot_bgcolor="#020617",
            paper_bgcolor="#020617",
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            hovermode="x unified",
            hoverlabel=dict(
                bgcolor="#000000",
                font_size=13,
                font_family="Monospace",
                bordercolor="#00ffbb"
            ),
            xaxis=dict(
                showspikes=True,
                spikemode="across",
                spikesnap="cursor",
                spikethickness=1,
                spikedash="dash",
                spikecolor="#666",
                type="category"
            ),
            yaxis=dict(side="right", gridcolor="rgba(255,255,255,0.05)")
        )

        hollow_json = json.dumps(hollow_candle,cls=PlotlyJSONEncoder)

        row_heights = [0.40, 0.1, 0.1, 0.1, 0.1, 0.1, 0.10]

        fig_candle = make_subplots(
            rows=7,
            cols=1,
            shared_xaxes=True,
            vertical_spacing=0.02,  # Boşluğu daralttık
            row_heights=row_heights,
            subplot_titles=(
                "Fiyat + İndikatörler",
                "Hacim",
                "Chaikin Oscillator",
                "RVI (Relative Vigor)",
                "NVI (Negative Volume Index)"
            ),
        )

        fig_candle.add_trace(
            go.Candlestick(
                x=x_ekseni,
                open=mum_open,
                high=mum_high,
                low=mum_low,
                close=mum_close,
                text=hacim_etiketleri,
                increasing_line_color="#00ffbb",
                decreasing_line_color="#ff4b5c",
                name="Mum",
            ),
            row=1,
            col=1,
        )

        for desen in desenler:
            son_mum_x = x_ekseni[-1]

            if "Çekiç" in desen:
                son_mum_y = df['Low'].iloc[-1]
                fig_candle.add_annotation(
                    x=son_mum_x, y=son_mum_y,
                    text="🔨 Çekiç",
                    showarrow=True, arrowhead=2,
                    arrowcolor="#00ffbb", ax=0, ay=30,
                    font=dict(color="#00ffbb", size=12),
                    bgcolor="rgba(0,0,0,0.8)"
                )

            if "Yutan Boğa" in desen:
                son_mum_y = df['Low'].iloc[-1]
                fig_candle.add_annotation(
                    x=son_mum_x, y=son_mum_y,
                    text="🔥 Yutan Boğa",
                    showarrow=True, arrowhead=2,
                    arrowcolor="#ffcc00", ax=0, ay=40,
                    font=dict(color="#ffcc00", size=12),
                    bgcolor="rgba(0,0,0,0.8)"
                )

        try:
            fig_candle.add_trace(
                go.Scatter(
                    x=x_ekseni,
                    y=ui_df[ui_col].fillna(0).values.flatten().tolist(),
                    mode="lines",
                    line=dict(color="#FF00FF", width=2),
                    name="Ulcer Index (Risk/Stres)",
                    visible='legendonly'
                ), row=6, col=1
            )

            fig_candle.add_hline(y=5, line_dash="dot", line_color="orange", row=6, col=1)

        except Exception as e:
            print(f"⚠️ Ulcer Index çizim hatası: {e}")

        try:
            if st_col and st_col in df.columns:
                st_vals = df[st_col].tolist()
                st_dirs = df[st_dir_col].tolist() if st_dir_col else [1] * len(st_vals)

                fig_candle.add_trace(go.Scatter(
                    x=x_ekseni,
                    y=[val if d > 0 else None for val, d in zip(st_vals, st_dirs)],
                    mode="lines",
                    line=dict(color="#00ffbb", width=2),
                    name="Supertrend (Al)",
                    visible='legendonly'
                ), row=1, col=1)

                # Kırmızı (Ayı) Hattı
                fig_candle.add_trace(go.Scatter(
                    x=x_ekseni,
                    y=[val if d < 0 else None for val, d in zip(st_vals, st_dirs)],
                    mode="lines",
                    line=dict(color="#ff4b5c", width=2),
                    name="Supertrend (Sat)",
                    visible='legendonly'
                ), row=1, col=1)
        except:
            pass

        try:
            if dcu_col and dcl_col:
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[dcu_col].fillna(0).values.flatten().tolist(),
                        mode="lines",
                        line=dict(color="rgba(255, 165, 0, 0.7)", width=1.5),
                        name="Donchian Üst",
                        visible='legendonly'
                    ),
                    row=1, col=1
                )
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[dcl_col].fillna(0).values.flatten().tolist(),
                        mode="lines",
                        line=dict(color="rgba(255, 165, 0, 0.7)", width=1.5),
                        fill='tonexty',
                        fillcolor='rgba(255, 165, 0, 0.05)',
                        name="Donchian Alt",
                        visible='legendonly'
                    ),
                    row=1, col=1
                )
            if dcm_col:
                # Orta Hat
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[dcm_col].fillna(0).values.flatten().tolist(),
                        mode="lines",
                        line=dict(color="rgba(255, 165, 0, 0.5)", width=1, dash="dash"),
                        name="Donchian Orta",
                        visible='legendonly'
                    ),
                    row=1, col=1
                )
        except:
            pass

        if trix_col and trix_col in df.columns:
            try:
                fig_candle.add_trace(
                    go.Scatter(x=x_ekseni, y=df[trix_col].fillna(0).values.flatten().tolist(),
                               name="TRIX", line=dict(color="#00fbff", width=2),
                               visible='legendonly'),
                    row=4, col=1
                )
                # TRIX Sinyal Çizgisi
                fig_candle.add_trace(
                    go.Scatter(x=x_ekseni, y=df[trix_sig_col].fillna(0).values.flatten().tolist(),
                               name="TRIX",
                               line=dict(color="#ff9900", width=1, dash='dot'),
                               visible='legendonly'),
                    row=4, col=1
                )
                fig_candle.add_hline(y=0, line_dash="dash", line_color="gray", row=4, col=1)
            except:
                pass

        bear_vals = df['BEAR_5'].fillna(0).values.flatten().tolist()
        fig_candle.add_trace(
            go.Scatter(
                x=x_ekseni,
                y=[h + (h * 0.002) if v else None for v, h in zip(bear_vals, mum_high)],
                mode="markers",
                marker=dict(symbol="triangle-down", size=10, color="#ff4b5c"),
                name="Fractal Bear (Direnç)",
                visible='legendonly'
            ),
            row=1, col=1
        )
        bull_vals = df['BULL_5'].fillna(0).values.flatten().tolist()
        fig_candle.add_trace(
            go.Scatter(
                x=x_ekseni,
                y=[l - (l * 0.002) if v else None for v, l in zip(bull_vals, mum_low)],
                mode="markers",
                marker=dict(symbol="triangle-up", size=10, color="#00ffbb"),
                name="Fractal Bull (Destek)",
                visible='legendonly'
            ),
            row=1, col=1
        )

        if smi_col:
            fig_candle.add_trace(
                go.Scatter(x=x_ekseni, y=smi_df_data[smi_col].fillna(0).values.flatten().tolist(), mode='lines',
                           name='SMI', line=dict(color="#00d2ff", width=2), visible='legendonly'), row=3, col=1)
            fig_candle.add_trace(
                go.Scatter(
                    x=x_ekseni,
                    y=smi_df_data[smi_sig_col].fillna(0).values.flatten().tolist(),
                    mode="lines",
                    line=dict(color="#ff9f43", width=1.5, dash="dot"),
                    name="SMI Signal",
                    visible='legendonly'
                ),
                row=3, col=1
            )

        try:
            if aroon_up_col and aroon_down_col:
                fig_candle.add_trace(
                    go.Scatter(x=x_ekseni, y=df[aroon_up_col].fillna(0).values.flatten().tolist(),
                               name="Aroon Up (Boğa)", line=dict(color="#00ffbb", width=2)),
                    row=6, col=1
                )
                fig_candle.add_trace(
                    go.Scatter(x=x_ekseni, y=df[aroon_down_col].tolist(),
                               name="Aroon Down (Ayı)", line=dict(color="#ff4b5c", width=2)),
                    row=6, col=1
                )
                fig_candle.add_hline(y=70, line_dash="dot", line_color="rgba(255,255,255,0.2)", row=6, col=1)
                fig_candle.add_hline(y=30, line_dash="dot", line_color="rgba(255,255,255,0.2)", row=6, col=1)

                fig_candle.add_hline(y=0, line_dash="dash", line_color="white", row=7, col=1)
        except:
            pass

        try:
            fig_candle.add_trace(go.Scatter(
                x=x_ekseni, y=df['SMA50'].fillna(0).values.flatten().tolist(),
                name="SMA 50", line=dict(color="#3b82f6", width=2),
                visible='legendonly'
            ), row=1, col=1)
        except:
            pass

        try:
            fig_candle.add_trace(go.Scatter(
                x=x_ekseni, y=df['SMA200'].fillna(0).values.flatten().tolist(),
                name="SMA 200", line=dict(color="#f59e0b", width=2),
                visible='legendonly'
            ), row=1, col=1)
        except:
            pass

        try:
            if gold_cross.any():
                fig_candle.add_trace(go.Scatter(
                    x=df[gold_cross].index, y=df[gold_cross]['SMA50'].fillna(0).values.flatten().tolist(),
                    mode="markers", marker=dict(symbol="triangle-up", size=15, color="#00ffbb"),
                    name="MA CROSS (GOLD)", hovertext="Golden Cross: Yükseliş Sinyali",
                    visible='legendonly'
                ), row=1, col=1)
        except:
            pass

        try:
            if death_cross.any():
                fig_candle.add_trace(go.Scatter(
                    x=df[death_cross].index, y=df[death_cross]['SMA50'].fillna(0).values.flatten().tolist(),
                    mode="markers", marker=dict(symbol="triangle-down", size=15, color="#ff4b5c"),
                    name="MA CROSS (DEATH)", hovertext="Death Cross: Düşüş Sinyali",
                    visible='legendonly'
                ), row=1, col=1)
        except:
            pass

        try:
            if ui_col and ui_col in df.columns:
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[ui_col].fillna(0).values.flatten().tolist(),
                        mode="lines",
                        line=dict(color="#ff00ff", width=2),
                        name="Ulcer Index",
                        visible='legendonly'
                    ),
                    row=3, col=1
                )
        except:
            pass


        for val, color in [(40, "red"), (0, "gray"), (-40, "green")]:
            fig_candle.add_hline(y=val, line_dash="dash", line_color=color, row=3, col=1)
        try:
            coppock = df.ta.coppock(roc1=11, roc2=14, wma=10)
            if coppock is not None:
                if isinstance(coppock, pd.Series):
                    df['COPC'] = coppock
                    copc_col = 'COPC'
                else:
                    df = pd.concat([df, coppock], axis=1)
                    copc_col = coppock.columns[0]
        except Exception:
            copc_col = None

        if cmo_col:
            fig_candle.add_trace(go.Scatter(x=x_ekseni, y=df[cmo_col].fillna(0).values.flatten().tolist(), mode='lines',
                                            line=dict(color='#FFD700', width=2), name='Chande Momentum Osc',
                                            visible='legendonly'), row=2, col=1)
        for val, color in [(50, 'green'), (0, 'gray'), (-50, 'red')]:
            fig_candle.add_hline(y=val, line_dash='dash', line_color=color, row=2, col=1)

        fig_candle.add_trace(
            go.Scatter(x=x_ekseni, y=df['Zarf_Ust'].fillna(0).values.flatten().tolist(),
                       line=dict(color='#3b82f6', width=1, dash='dot'),
                       name='Zarf Üst', visible='legendonly'),
            row=1, col=1
        )
        fig_candle.add_trace(
            go.Scatter(x=x_ekseni, y=df['Zarf_Alt'].fillna(0).values.flatten().tolist(),
                       line=dict(color='#3b82f6', width=1, dash='dot'),
                       name='Zarf Alt', visible='legendonly',
                       fill='tonexty', fillcolor='rgba(59, 130, 246, 0.05)'),
            row=1, col=1
        )

        ribbon_colors = ['#00ffbb', '#2ecc71', '#27ae60', '#f1c40f', '#f39c12', '#e67e22', '#e74c3c', '#c0392b']

        try:
            for i, length in enumerate(ema_lengths):
                ema_col_name = f'EMA_{length}'
                if ema_col_name in df.columns:
                    fig_candle.add_trace(
                        go.Scatter(
                            x=x_ekseni,
                            y=df[ema_col_name].fillna(0).values.flatten().tolist(),
                            mode="lines",
                            line=dict(color=ribbon_colors[i], width=1.3),
                            name=f"EMA {length}",
                            visible='legendonly',
                            connectgaps=False
                        ),
                        row=1, col=1
                    )
        except:
            pass

        if kst_col is not None and kst_col in df.columns:
            try:
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[kst_sig_col].fillna(0).tolist(),
                        mode="lines",
                        line=dict(color="#ffffff", width=1.5, dash="dot"),  # Beyaz Kesikli
                        name="KST Sinyal",
                        visible='legendonly'
                    ), row=5, col=1
                )

            except:
                pass

        if rsi_col and rsi_col in df.columns:
            fig_candle.add_trace(
                go.Scatter(
                    x=x_ekseni,
                    y=df[rsi_col].fillna(50).values.flatten().tolist(),
                    mode="lines",
                    line=dict(color="#ffffff", width=2),
                    name="RSI",
                    visible='legendonly'
                ),
                row=3, col=1
            )

            fig_candle.add_hline(y=70, line_dash="dot", line_color="rgba(255, 75, 92, 0.5)", row=2, col=1)
            fig_candle.add_hline(y=30, line_dash="dot", line_color="rgba(0, 255, 187, 0.5)", row=2, col=1)

        fig_candle.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)", row=5, col=1)

        if kst_sig_col is not None and kst_sig_col in df.columns:
            try:
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[kst_sig_col].fillna(0).values.flatten().tolist(),
                        mode="lines",
                        line=dict(color="#ffffff", width=1.5, dash="dot"),
                        name="KST Sinyal",
                        visible='legendonly'
                    ), row=5, col=1
                )
            except:
                pass

        if psar_l_col and psar_s_col:
            fig_candle.add_trace(
                go.Scatter(
                    x=x_ekseni,
                    y=psar_df[psar_l_col].fillna(0).values.flatten().tolist(),
                    mode='markers',
                    marker=dict(symbol="circle", size=4, color="#00ffbb"),
                    name='PSAR BULL',
                    visible='legendonly'), row=1, col=1)

        if tsi_df is not None and tsi_col and tsi_col in df.columns:
            try:
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[tsi_col].fillna(0).tolist(),
                        mode="lines",
                        line=dict(color="#00d2ff", width=2),
                        name="TSI (Gerçek Güç)",
                        visible='legendonly'
                    ), row=5, col=1
                )

                if tsi_sig_col and tsi_sig_col in df.columns:
                    fig_candle.add_trace(
                        go.Scatter(
                            x=x_ekseni,
                            y=df[tsi_sig_col].fillna(0).tolist(),
                            mode="lines",
                            line=dict(color="#ff9f43", width=1.5, dash="dot"),
                            name="TSI Sinyal",
                            visible='legendonly'
                        ), row=5, col=1
                    )

                fig_candle.add_hline(y=0, line_dash="dash", line_color="gray", row=5, col=1)
            except Exception as e:
                print(f'TSI çizim hatası: {e}')

        if lrc_col is not None and lrc_col in df.columns:
            try:
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[lrc_col].fillna(0).tolist(),
                        mode="lines",
                        line=dict(color="#FF00FF", width=2, dash="solid"),  # Parlak Magenta rengi
                        name="Regresyon Eğrisi (LRC)",
                        visible='legendonly'
                    ), row=1, col=1
                )
            except:
                pass

        if nvi_col in df.columns:
            try:
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[nvi_col].fillna(0).values.flatten().tolist(),
                        mode="lines",
                        line=dict(color="#ffffff", width=2),
                        name="NVI",
                        visible='legendonly'
                    ),
                    row=5, col=1
                )
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[nvi_sig_col].tolist(),
                        mode="lines",
                        line=dict(color="#ffcc00", width=1.5, dash="dash"),
                        name="NVI Signal",
                        visible='legendonly'
                    ),
                    row=5, col=1
                )
            except:
                pass

        try:
            if cks_l_col:
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[cks_l_col].fillna(0).values.flatten().tolist(),
                        mode="lines",
                        line=dict(color="rgba(0, 255, 187, 0.6)", width=1.5, dash="dash"),
                        name="CKS Long Stop",
                        connectgaps=False, visible='legendonly'
                    ),
                    row=1, col=1
                )
            else:
                pass
        except:
            pass

        if ce_ready:
            fig_candle.add_trace(go.Scatter(
                x=x_ekseni, y=df['Chandelier_Long'].fillna(0).values.flatten().tolist(),
                name="Chandelier Long",
                line=dict(color="#00ffbb", width=1.5, dash="dot"),
                visible='legendonly',
                connectgaps=False
            ), row=1, col=1)

            fig_candle.add_trace(go.Scatter(
                x=x_ekseni, y=df['Chandelier_Short'].fillna(0).values.flatten().tolist(),
                name="Chandelier Short",
                line=dict(color="#ff4b5c", width=1.5, dash="dot"),
                visible='legendonly',
                connectgaps=False
            ), row=1, col=1)

        try:
            if dpo_col and dpo_col in df.columns:
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[dpo_col].fillna(0).values.flatten().tolist(),
                        mode="lines",
                        line=dict(color="#FF8C00", width=2),
                        name="Trend Azaltma Fiyat Osilatörü (DPO)",
                        visible='legendonly'
                    ), row=7, col=1
                )
                fig_candle.add_hline(y=0, line_dash="dash", line_color="white", row=7, col=1)
        except:
            pass

        if aroon_up_col and aroon_down_col:
            fig_candle.add_trace(
                go.Scatter(x=x_ekseni, y=df[aroon_up_col].fillna(0).values.flatten().tolist(),
                           name="Aroon Up (Boğa)", line=dict(color="#00ffbb", width=2)),
                row=5, col=1
            )
            fig_candle.add_trace(
                go.Scatter(x=x_ekseni, y=df[aroon_down_col].fillna(0).values.flatten().tolist(),
                           name="Aroon Down (Ayı)", line=dict(color="#ff4b5c", width=2)),
                row=5, col=1
            )

            fig_candle.add_hline(y=70, line_dash="dot", line_color="rgba(255,255,255,0.2)", row=5, col=1)
            fig_candle.add_hline(y=30, line_dash="dot", line_color="rgba(255,255,255,0.2)", row=5, col=1)


        if aroon_osc_col:
            fig_candle.add_trace(
                go.Scatter(x=x_ekseni, y=df[aroon_osc_col].fillna(0).values.flatten().tolist(),
                           fill='tozeroy', name="Aroon Oscillator",
                           line=dict(color="#3b82f6", width=1.5),
                           fillcolor="rgba(59, 130, 246, 0.2)"),
                row=6, col=1
            )
            fig_candle.add_hline(y=0, line_dash="dash", line_color="white", row=6, col=1)

        try:
            if pmo_col and pmo_sig_col:
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[pmo_col].fillna(0).values.flatten().tolist(),
                        mode="lines",
                        line=dict(color="#9b59b6", width=2),
                        name="PMO",
                        visible='legendonly'
                    ),
                    row=3, col=1
                )

            fig_candle.add_trace(
                go.Scatter(
                    x=x_ekseni,
                    y=df[pmo_sig_col].fillna(0).values.flatten().tolist(),
                    mode="lines",
                    line=dict(color="rgba(255,255,255,0.6)", width=1.5, dash="dot"),
                    name="PMO Signal",
                    visible='legendonly'
                ),
                row=3, col=1
            )
        except:
            pass

        if copc_col:
            try:
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[copc_col].values.flatten().tolist(),
                        name="Coppock Curve",
                        mode="lines",
                        line=dict(color="#FF8C00", width=2.5),
                        visible='legendonly'), row=6, col=1)
                fig_candle.add_hline(y=0, line_dash="dash", line_color="white", row=2, col=1)
            except:
                pass
        else:
            pass

        try:
            if isinstance(spk_df, pd.DataFrame) and spk_col in spk_df.columns:
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=spk_df[spk_col].fillna(0).values.flatten().tolist(),
                        mode="lines",
                        line=dict(color="#FF8C00", width=2.5),
                        name="Special K",
                        visible='legendonly'), row=3, col=1)
            else:
                pass
        except:
            pass

        fig_candle.add_hline(y=0, line_dash="dash", line_color="#ffffff", row=3, col=1)

        if isinstance(rvi_df, pd.Series):
            rvi_df = rvi_df.to_frame()

        knox_bull_points = pd.DataFrame()
        knox_bear_points = pd.DataFrame()

        if rvi_sig_col and rvi_sig_col in df.columns:
            try:
                df = knoxville_divergence(df, osc_col=rvi_sig_col)

                # Filtreleme yaparken kopyasını al (Memory leak ve Gaps hatasını önler)
                if "knox_bull" in df.columns:
                    knox_bull_points = df[df["knox_bull"] == True].copy()

                if "knox_bear" in df.columns:
                    knox_bear_points = df[df["knox_bear"] == True].copy()
            except Exception:
                pass
            if not knox_bear_points.empty:
                try:
                    fig_candle.add_trace(
                        go.Scatter(
                            x=knox_bear_points.index.strftime(date_fmt).tolist(),
                            y=(knox_bear_points["High"] * 1.01).tolist(),
                            mode="markers",
                            marker=dict(symbol="diamond", size=8, color="#ff0000"),
                            name="Knoxville Bear",
                            visible="legendonly",
                        ),
                        row=1,
                        col=1,
                    )
                except:
                    pass
            else:
                pass

        knox_bull_points = df[df["knox_bull"] == True]
        if not knox_bull_points.empty:
            try:
                fig_candle.add_trace(
                    go.Scatter(
                        x=knox_bull_points.index.strftime(date_fmt).tolist(),
                        y=(knox_bull_points["Low"] * 0.99).tolist(),
                        mode="markers",
                        marker=dict(symbol="diamond", size=10, color="#00ff00"),
                        name="Knoxville Bull 🐂",
                        visible="legendonly",
                    ), row=1, col=1
                )
            except:
                pass
        try:
            fig_candle.add_trace(
                go.Scatter(
                    x=x_ekseni,
                    y=rvi_df[rvi_sig_col].fillna(0).values.flatten().tolist(),
                    mode="lines",
                    line=dict(color="#ff4500", width=1.5, dash="dot"),
                    name="RVI Signal",
                    visible='legendonly', connectgaps=False,
                ),
                row=4, col=1
            )
        except Exception:
            pass

        if cks_s_col:
            fig_candle.add_trace(
                go.Scatter(
                    x=x_ekseni,
                    y=df[cks_s_col].fillna(0).values.flatten().tolist(),
                    mode="lines",
                    line=dict(color="rgba(255, 75, 92, 0.6)", width=1.5, dash="dash"),
                    name="CKS Short Stop",
                    connectgaps=False, visible='legendonly'
                ),
                row=1, col=1
            )

        if bbu_col:
            fig_candle.add_trace(
                go.Scatter(
                    x=x_ekseni,
                    y=df[bbu_col].values.flatten().tolist(),
                    mode="lines",
                    line=dict(color="rgba(59, 130, 246, 0.8)", width=1.5, dash="dot"),
                    name="BB Üst",
                    connectgaps=False, visible='legendonly',
                ),
                row=1,
                col=1,
            )

        if kama_col:
            fig_candle.add_trace(
                go.Scatter(
                    x=x_ekseni,
                    y=df[kama_col].values.flatten().tolist(),
                    mode='lines',
                    line=dict(color="#e91e63", width=2),
                    name='KAMA',
                    visible='legendonly'
                ), row=1, col=1)

        if bbm_col:
            fig_candle.add_trace(
                go.Scatter(
                    x=x_ekseni,
                    y=df[bbm_col].values.flatten().tolist(),
                    mode="lines",
                    line=dict(color="rgba(148, 163, 184, 0.9)", width=1),
                    name="BB Orta",
                    connectgaps=False, visible='legendonly',
                ),
                row=1,
                col=1,
            )
        if bbl_col:
            fig_candle.add_trace(
                go.Scatter(
                    x=x_ekseni,
                    y=df[bbl_col].values.flatten().tolist(),
                    mode="lines",
                    line=dict(color="rgba(59, 130, 246, 0.8)", width=1.5, dash="dot"),
                    name="BB Alt",
                    connectgaps=False, visible='legendonly',
                ),
                row=1,
                col=1,
            )

        # WMA
        try:
            if wma_col:
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[wma_col].values.flatten().tolist(),
                        mode="lines",
                        line=dict(color="#3498db", width=2, dash="dot"),
                        name="WMA (9)", visible='legendonly',
                        connectgaps=False,
                    ),
                    row=1,
                    col=1,
                )
        except:
            pass

        try:
            if alma_col:
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[alma_col].values.flatten().tolist(),
                        mode="lines",
                        line=dict(color="#FFD700", width=2),
                        name="ALMA (9)", visible='legendonly',
                        connectgaps=False,
                    ),
                    row=1,
                    col=1,
                )
        except:
            pass

        try:
            if isa_col and isb_col:
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[isa_col].values.flatten().tolist(),
                        mode="lines",
                        line=dict(color="rgba(34, 197, 94, 0.4)", width=1),
                        name="Ichimoku Span A",
                        fill=None, visible='legendonly',
                        connectgaps=False,
                    ),
                    row=1,
                    col=1,
                )

                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[isb_col].values.flatten().tolist(),
                        mode="lines",
                        line=dict(color="rgba(239, 68, 68, 0.4)", width=1),
                        name="Ichimoku Span B",
                        fill="tonexty",
                        connectgaps=False, visible='legendonly',
                    ),
                    row=1,
                    col=1,
                )
        except:
            pass

        vol_colors = ["#00ffbb" if mum_close[i] >= mum_open[i] else "#ff4b5c" for i in range(n)]
        fig_candle.add_trace(
            go.Bar(
                x=x_ekseni,
                y=volume_values,
                marker_color=vol_colors,
                marker_line_width=0,
                hovertext=hacim_etiketleri,
                hoverinfo="text",
                name="Hacim",
            ),
            row=2,
            col=1,
        )
        fig_candle.add_hline(y=0, line_dash="dash", line_color="rgba(148,163,184,0.5)", row=2, col=1)

        if adosc_col:
            try:
                cho_vals = df[adosc_col].tolist()
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=cho_vals,
                        mode="lines",
                        line=dict(color="#e74c3c", width=2),
                        name="Chaikin Osc",
                        connectgaps=False, visible='legendonly'
                    ),
                    row=3,
                    col=1,
                )
            except:
                pass
        else:
            pass

            try:
                if bear_col:
                    bear_vals = df[bear_col].fillna(0).values.flatten().tolist()
                    fig_candle.add_trace(
                        go.Scatter(
                            x=x_ekseni,
                            y=[h + (h * 0.002) if v else None for v, h in zip(bear_vals, mum_high)],
                            mode="markers",
                            marker=dict(symbol="triangle-down", size=10, color="#ff4b5c"),
                            name="Fractal Bear (Direnç)",
                            hoverinfo="skip", visible='legendonly',
                        ),
                        row=1, col=1
                    )
            except:
                pass

                try:
                    if uo_col:
                        fig_candle.add_trace(
                            go.Scatter(
                                x=x_ekseni,
                                y=df[uo_col].fillna(0).values.flatten().tolist(),
                                mode='lines',
                                line=dict(color="#00ffff", width=2, dash="dashdot"),
                                name="Ultimate Osc",
                                visible='legendonly',
                            ), row=3, col=1)
                        for val, color in [(70, "red"), (30, "green")]:
                            fig_candle.add_hline(y=val, line_dash="dot", line_color=color, row=3, col=1)
                except Exception as e:
                    print(e)
                    pass

                try:
                    if bull_col:
                        bull_vals = df[bull_col].fillna(0).values.flatten()
                        fig_candle.add_trace(
                            go.Scatter(
                                x=x_ekseni,
                                y=[l - (l * 0.002) if v else None for v, l in zip(bull_vals, mum_low)],
                                mode="markers",
                                marker=dict(symbol="triangle-up", size=10, color="#00ffbb"),
                                name="Fractal Bull (Destek)",
                                hoverinfo="skip", visible='legendonly'
                            ),
                            row=1, col=1
                        )
                except:
                    pass
        try:
            if rvi_col:
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[rvi_col].fillna(0).values.flatten().tolist(),
                        mode="lines",
                        line=dict(color="#32cd32", width=2),
                        name="RVI",
                        visible="legendonly",
                    ),
                    row=4,
                    col=1,
                )
        except:
            pass

        if hv_col and hv_col in df.columns:
            fig_candle.add_trace(
                go.Scatter(
                    x=x_ekseni,
                    y=df[hv_col].fillna(0).values.flatten().tolist(),
                    mode="lines",
                    line=dict(color="#FFD700", width=2),
                    name="Volatilite (HV)",  # HTML'deki 'Volatilite' ile birebir aynı
                    visible='True'
                ),
                row=7, col=1
            )
        try:
            if rvi_sig_col:
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[rvi_sig_col].fillna(0).values.flatten().tolist(),
                        mode="lines",
                        line=dict(color="#ff4500", width=1.5, dash="dot"),
                        name="RVI Signal",
                        visible="legendonly",
                    ),
                    row=4,
                    col=1,
                )
        except:
            pass

        if trix_col and trix_col in df.columns:
            try:
                # TRIX Ana Çizgi
                fig_candle.add_trace(
                    go.Scatter(
                        x=x_ekseni,
                        y=df[trix_col].fillna(0).values.flatten().tolist(),
                        mode="lines",
                        line=dict(color="#00e5ff", width=2),
                        name="TRIX", visible='legendonly'
                    ), row=5, col=1  # Hangi satıra koymak istiyorsan
                )

                try:
                    if trix_sig_col and trix_sig_col in df.columns:
                        fig_candle.add_trace(
                            go.Scatter(
                                x=x_ekseni,
                                y=df[trix_sig_col].fillna(0).values.flatten().tolist(),
                                mode="lines",
                                line=dict(color="#ff9100", width=1, dash="dot"),
                                name="TRIX Sinyal", visible='legendonly',
                            ), row=5, col=1
                        )
                except:
                    pass

                fig_candle.add_hline(y=0, line_dash="dash", line_color="gray", row=5, col=1)

            except Exception as e:
                print(f"TRIX çizim hatası: {e}")
        fig_candle.add_hline(y=0, line_dash="dash", line_color="gray", row=3, col=1)
        ha_df = df.ta.ha()
        if isinstance(ha_df.columns, pd.DataFrame):
            ha_df.columns = ha_df.columns.get_level_values()

        ha_open = ha_df["HA_open"].values.flatten().tolist()
        ha_high = ha_df["HA_high"].values.flatten().tolist()
        ha_low = ha_df["HA_low"].values.flatten().tolist()
        ha_close = ha_df["HA_close"].values.flatten().tolist()
        fig_alan = go.Figure()

        fig_alan.add_trace(
            go.Scatter(
                x=x_ekseni,
                y=mum_close,
                mode="lines",
                line=dict(color=ana_renk, width=3, shape='spline'),
                fill="tozeroy",
                fillcolor=dolgu_renk,
                name="Fiyat Akışı",
                hoverinfo="x+y"
            )
        )

        fig_alan.update_layout(
            template="plotly_dark",
            height=400,
            title=dict(
                text=f"{sembol} - Fiyat Alan Analizi",
                x=0.5, font=dict(color=ana_renk, size=18)
            ),
            hovermode="x unified",
            hoverlabel=dict(
                bgcolor="#0f172a",
                font_size=13,
                font_family="Fira Code",
                font_color=ana_renk
            ),
            xaxis=dict(
                type="category",
                gridcolor="rgba(255,255,255,0.05)",
                showspikes=True,
                spikemode="across",
                spikethickness=1,
                spikedash="dot",
                spikecolor="#94a3b8"
            ),
            yaxis=dict(gridcolor="rgba(255,255,255,0.05)", side="right"),
            paper_bgcolor="#020617",
            plot_bgcolor="#020617",
            margin=dict(l=20, r=20, t=60, b=20)
        )

        alan_json = json.dumps(fig_alan,cls=PlotlyJSONEncoder)

        fig_heikin = go.Figure()
        fig_heikin.add_trace(
            go.Candlestick(
                x=x_ekseni,
                open=ha_open,
                high=ha_high,
                low=ha_low,
                close=ha_close,
                increasing_line_color="#00ffbb",
                decreasing_line_color="#ff4b5c",
                name="Heikin Ashi"
            )
        )
        fig_heikin.update_layout(
            template="plotly_dark",
            height=800,
            paper_bgcolor="#020617",
            plot_bgcolor="#020617",
            hovermode="x unified",
            hoverlabel=dict(bgcolor="#0f172a", font_size=13, font_family="Fira Code"),
            xaxis=dict(
                type='category',
                rangeslider_visible=False,
                showspikes=True,
                spikemode="across",
                spikethickness=1,
                spikedash="dot",
                spikecolor="#94a3b8"
            )
        )

        heikin_json = json.dumps(fig_heikin,cls=PlotlyJSONEncoder)
        del fig_heikin

        fig_candle.update_layout(
            template="plotly_dark",
            paper_bgcolor="#020617",
            plot_bgcolor="#020617",
            hovermode="x unified",
            height=800,
            margin=dict(l=50, r=40, t=50, b=50),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        fig_candle.update_xaxes(
            type="category",
            tickangle=-45,
            nticks=min(20, n),
            rangeslider_visible=False,
            gridcolor="rgba(255,255,255,0.05)",
        )
        fig_candle.update_yaxes(gridcolor="rgba(255,255,255,0.05)", side="right")
        fig_candle.update_yaxes(title_text="Hacim", row=2, col=1)
        fig_candle.update_yaxes(title_text="CHO", row=3, col=1)
        last_rvi = float(rvi_df[rvi_col].iloc[-1]) if rvi_col and rvi_df is not None else "Veri Yok"
        last_smi = float(smi_df_data[smi_col].iloc[-1]) if smi_col else "Veri Yok"
        try:
            last_kama = float(df[kama_col].iloc[-1]) if kama_col else "Veri Yok"
        except:
            last_kama = np.nan
        if isinstance(spk_df, pd.DataFrame) and spk_col in spk_df.columns:
            last_spk = float(spk_df[spk_col].iloc[-1])
        else:
            last_spk = "700+ Mum Gerekli / Hesaplanmadı"
        psar_durum = "BOĞA (Yükseliş)" if (psar_l_col and not pd.isna(psar_df[psar_l_col].iloc[-1])) else "AYI (Düşüş)"

        if nvi_col in df.columns and nvi_sig_col in df.columns:
            try:
                if df[nvi_col].iloc[-1] > df[nvi_sig_col].iloc[-1]:
                    nvi_analiz_durumu = "Boğa (Akıllı Para Alımda)"
                else:
                    nvi_analiz_durumu = "Ayı (Zayıf Görünüm)"
            except Exception as e:
                print(f"NVI Karşılaştırma Hatası: {e}")

        try:
            aroon_durum = "Yatay Piyasa"
            if aroon_up_col and aroon_down_col:
                up_val = df[aroon_up_col].iloc[-1]
                down_val = df[aroon_down_col].iloc[-1]

                if up_val > 70 and down_val < 30:
                    aroon_durum = "Güçlü Yükseliş Trendi 🔥"
                elif down_val > 70 and up_val < 30:
                    aroon_durum = "Güçlü Düşüş Trendi ❄️"
                elif up_val > down_val:
                    aroon_durum = "Yükseliş Hazırlığı"
                else:
                    aroon_durum = "Düşüş Baskısı".env
        except:
            aroon_durum = 'Hesaplanamadı'
            up_val = None
            down_val = None

        def guvenli_float_hesapla(deger, varsayilan="Hesaplanamadı", yuvarlama=4):
            try:
                if deger is not None:
                    return round(float(deger), yuvarlama)
            except:
                pass
            return varsayilan

        def guvenli_series_hesapla(df, kolon, varsayilan="Hesaplanamadı", yuvarlama=4):
            try:
                if kolon and kolon in df.columns and len(df) > 0:
                    deger = df[kolon].iloc[-1]
                    if hasattr(deger, 'values') and len(deger.values) > 0:
                        return round(float(deger.values.flatten()[0]), yuvarlama)
                    elif not pd.isna(deger):
                        return round(float(deger), yuvarlama)
            except:
                pass
            return varsayilan

        def guvenli_df_hesapla(df, kolon, varsayilan="Hesaplanamadı", yuvarlama=4):
            try:
                if df is not None and kolon and kolon in df.columns and len(df) > 0:
                    deger = df[kolon].iloc[-1]
                    if not pd.isna(deger):
                        return round(float(deger), yuvarlama)
            except:
                pass
            return varsayilan

        try:
            ai_ozet_veri = {
                "sembol": val_ex(sembol),
                "periyot": val_ex(period),
                "zaman_dilimi": val_ex(interval),
                "son_fiyat": val_ex(son_fiyat),
                "ath_seviyesi": val_ex(ath),
                "atl_seviyesi": val_ex(atl),
                "adx_degeri": val_ex(last_adx),
                "alma_değeri": val_ex(round(last_alma, 2) if last_alma is not None else "Hesaplanamadı"),
                "alma_notu": val_ex(alma_notu),
                "Son Cho Değeri": val_ex(last_cho),
                "Cho Notu": val_ex(cho_notu),
                "ichimoku_analizi": val_ex("\n".join(analiz_maddeleri) if analiz_maddeleri else ""),
                "bollinger_bantlari": {
                    "ust_bant": val_ex(round(bb_upper, 2) if bb_upper is not None else "Hesaplanamadı"),
                    "orta_bant": val_ex(round(bb_middle, 2) if bb_middle is not None else "Hesaplanamadı"),
                    "alt_bant": val_ex(round(bb_lower, 2) if bb_lower is not None else "Hesaplanamadı"),
                    "durum": val_ex(bb_notu),
                },
                "trend_durumu": val_ex("GÜÇLÜ" if last_adx and last_adx > 25 else "ZAYIF/YATAY"),

                "momentum_ve_dongu": {
                    "RVI_Göreceli_Canlılık": val_ex(guvenli_df_hesapla(rvi_df, rvi_col)),
                    "SMI_Momentum_Endeksi": val_ex(guvenli_df_hesapla(smi_df_data, smi_col)),
                    "dpo_analizi": {
                        "deger": val_ex(guvenli_series_hesapla(df, dpo_col)),
                        "sinyal": val_ex("Pozitif (Trend Üstü)" if (
                                dpo_col and dpo_col in df.columns and len(df) > 0 and df[dpo_col].iloc[-1] > 0)
                                         else "Negatif (Trend Altı)") if dpo_col else val_ex("Negatif (Trend Altı)")
                    },
                },
                "fiyat_ve_ortalama": {
                    "KAMA_Kaufman_Ortalama": val_ex(guvenli_series_hesapla(df, kama_col, yuvarlama=2)),
                    "PSAR_BULL_Seviyesi": val_ex(
                        guvenli_df_hesapla(psar_df, psar_l_col, varsayilan="Aktif Değil", yuvarlama=2)),
                    "PSAR_BEAR_Seviyesi": val_ex(
                        guvenli_df_hesapla(psar_df, psar_s_col, varsayilan="Aktif Değil", yuvarlama=2)),
                },
                "momentum_cmo": val_ex(guvenli_series_hesapla(df, cmo_col, yuvarlama=2)),
                "hacim_ve_guc_endeksleri": {
                    "NVI_Negatif_Hacim": val_ex(guvenli_series_hesapla(df, nvi_col, yuvarlama=2)),
                    "TSI_True_Strength": val_ex(guvenli_series_hesapla(df, tsi_col)),
                    "TRIX_Triple_EMA": val_ex(guvenli_series_hesapla(df, trix_col, varsayilan="Veri Yetersiz")),
                },
                "risk_ve_stres_analizi": {
                    "Ulcer_Index_Stres": val_ex(guvenli_series_hesapla(df, ui_col, yuvarlama=2)),
                    "UO_Ultimate_Osc": val_ex(guvenli_series_hesapla(df, uo_col, yuvarlama=2)),
                },
                "trend_detay": {
                    "ADX_Trend_Gucu": val_ex(round(last_adx, 2) if adx_col and last_adx else 0),
                    "WMA_9_Seviyesi": val_ex(guvenli_series_hesapla(df, wma_col, yuvarlama=2)),
                },
                "mum_formasyonlari": val_ex(desenler if desenler else ["Belirgin bir formasyon saptanmadı"])
            }

            ai_ozet_veri["aroon_analizi"] = aroon_durum
            ai_ozet_veri["trend_detay"].update({
                "sma_50_seviyesi": val_ex(guvenli_series_hesapla(df, 'SMA50', yuvarlama=2)),
                "sma_200_seviyesi": val_ex(guvenli_series_hesapla(df, 'SMA200', yuvarlama=2)),
                "ma_cross_durumu": val_ex("GOLDEN CROSS (Boğa)" if gold_cross.iloc[-1] else
                                          "DEATH CROSS (Ayı)" if death_cross.iloc[-1] else "Nötr / Kesişim Yok")
            })

            ai_ozet_veri["hacim_ve_guc_endeksleri"].update({
                "williams_gator": {
                    "ust_deger": val_ex(guvenli_series_hesapla(df, 'Gator_Upper', yuvarlama=4)),
                    "alt_deger": val_ex(guvenli_series_hesapla(df, 'Gator_Lower', yuvarlama=4)),
                    "timsah_durumu": val_ex(
                        "AVLANMA (Güçlü Trend)" if (df['Gator_Upper'].iloc[-1] > df['Gator_Upper'].iloc[-2] and
                                                    df['Gator_Lower'].iloc[-1] < df['Gator_Lower'].iloc[-2])
                        else "UYKU/UYANMA (Yatay)")
                }
            })


            ai_ozet_veri["risk_ve_stres_analizi"].update({
                "chandelier_exit_long": val_ex(guvenli_series_hesapla(df, 'Chandelier_Long', yuvarlama=2)),
                "chandelier_exit_short": val_ex(guvenli_series_hesapla(df, 'Chandelier_Short', yuvarlama=2)),
                "iz süren_stop_notu": val_ex(
                    "STOP OL" if df['Close'].iloc[-1] < df['Chandelier_Long'].iloc[-1] else "Trend Takibinde")
            })

        except Exception as e:
            print(f"AI özet veri oluşturulurken hata: {e}")
            ai_ozet_veri = {
                "sembol": val_ex(sembol) if 'sembol' in locals() else "Bilinmiyor",
                "hata": 'Hata',
                "durum": "Veri hesaplanamadı"
            }

        candle_json = json.dumps(fig_candle,cls=PlotlyJSONEncoder)
        del fig_candle
        try:
            teknik_talimat = (
                f"Sen dünyanın en saygın yatırım bankalarında çalışan kıdemli bir fon yöneticisi ve baş stratejistsin. "
                f"Analizini mutlaka {dil} dilinde yapmalısın. Sana sağlanan ham teknik veri setini sadece listeleme; "
                                f"**ANALİZ EDİLECEK VERİ SETİ:** {ai_ozet_veri}"
                "bu verileri birbiriyle harmanlayarak derinlemesine bir 'Piyasa Okuması' gerçekleştir.\n\n"

                "### ANALİZ ÖNCELİKLERİN:\n"
                "1. **Trend ve Momentum Uyumu:** KAMA ve PSAR'ın fiyat üzerindeki baskısını, ADX'in trend gücüyle birleştir. "
                "SMI ve RVI gibi momentum göstergelerinin trendi destekleyip desteklemediğini açıkla.\n"
                "2. **Hacim ve Para Girişi:** Chaikin Oscillator (Cho), NVI ve TSI üzerinden 'akıllı paranın' (Smart Money) "
                "pozisyon alıp almadığını, hacmin fiyat hareketini onaylayıp onaylamadığını analiz et.\n"
                "3. **Risk ve Stres Değerlendirmesi:** Ulcer Index (Stres Endeksi) ve Ultimate Oscillator üzerinden "
                "mevcut volatilite riskini ve aşırı alım/satım yorgunluklarını tespit et.\n"
                "4. **İndikatör Çelişkileri:** Eğer Aroon trend gösterirken TRIX veya DPO negatifse bu uyumsuzluğu mutlaka belirt.\n\n"

                "### RAPORLAMA FORMATI:\n"
                "- **DETAY DÜZEYİ:** Her bir indikatörün ne anlama geldiğini, şu anki değerinin neyi ifade ettiğini 'Eğitici ve Profesyonel' bir dille anlat.\n"
                "- **UZUNLUK:** Çok detaylı ve kapsamlı bir analiz sun. Kullanıcıyı teknik terimlerin içinde boğma ama sığ bir analizden de kaçın.\n"
                "- **SENARYO ANALİZİ:** Mevcut tablodan çıkan en yüksek olasılıklı 'Boğa' veya 'Ayı' senaryosunu kurgula.\n"
                "- **KARAR MERKEZİ:** Analizin sonunda; Kısa, Orta ve Uzun vadeli getiri potansiyelini açıkça belirt. "
                "Kullanıcının mevcut durumda AL, SAT veya TUT kararlarından hangisinin risk/ödül dengesine göre daha mantıklı olduğunu rasyonel sebeplerle açıkla.\n\n"
            )
            ai_response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": teknik_talimat},
                    {"role": "user", "content": f"Teknik veri seti: {ai_ozet_veri}"},
                ],
                max_tokens=4000,
                temperature=0.6,
            )
            ai_analiz_notu = ai_response.choices[0].message.content
        except Exception:
            pass

        ticker = yf.Ticker(sembol)
        long_name = ticker.info.get("longName", sembol)

        return render_template(
            "analizpaneli.html",
            kapanıs=son_fiyat,
            ai_analiz_notu=ai_analiz_notu,
            zirveden_uzaklık=zirveden_uzaklık,
            line_json=fig_line,
            candle_json=candle_json,
            bar_json=bar_json,
            candle_volume_json=fig_candle_volume_json,
            heikin_ashi_json=heikin_json,
            area_json=alan_json,
            hollow_candle_json=hollow_json,
            hisse=sembol,
            fiyat_son=round(float(son_fiyat), 2),
            fiyat_degisim=round(((son_fiyat / ilk_fiyat) - 1) * 100, 2),
            ath=ath,
            atl=atl)

    except KeyError as e:
        return f"<h1>📊 Veri Formatı Hatası</h1><p>Borsadan gelen verilerde beklenen  veri bulunamadı.</p>"
    except requests.exceptions.Timeout:
        return "<h1>⌛ Sunucu Yanıt Vermiyor</h1><p>Veri kaynağı (Yahoo Finance/Borsa) çok geç yanıt veriyor, lütfen tekrar deneyin.</p>"

    except (requests.exceptions.ConnectionError, ConnectionError):
        return "<h1>🌐 Bağlantı Hatası</h1><p>İnternet bağlantınızı kontrol edin veya veri sağlayıcısının erişilebilir olduğundan emin olun.</p>"

    except ZeroDivisionError:
        return "<h1>🧮 Matematiksel Hata</h1><p>Veri setindeki eksiklikler nedeniyle finansal rasyolar hesaplanamadı (Sıfıra bölme hatası).</p>"

    except pd.errors.EmptyDataError:
        return "<h1>📉 Veri Boş</h1><p>Arattığınız hisse/kripto için geçmiş fiyat verisi bulunamadı.</p>"

    except ccxt.ExchangeError:
        return "<h1>🏛️ Borsa API Hatası</h1><p>Kripto borsasından veri çekilirken borsa kaynaklı bir hata oluştu.</p>"

    except ccxt.AuthenticationError:
        return "<h1>🔑 Yetkilendirme Hatası</h1><p>Borsa API anahtarlarınız hatalı veya süresi dolmuş.</p>"

    except PermissionError:
        return "<h1>🔒 Erişim Yetkisi Yok</h1><p>Sistem dosyalarına veya veritabanına erişim izniniz bulunmuyor.</p>"

    except Exception as e:
        print(e)
        return f"<h1>🛠️ Beklenmedik Bir Hata</h1><p>Sistem yöneticisine iletilmek üzere kaydedildi./p>"
    finally:
        df_list = [
            'df', 'ichi_df', 'smi_df_data', 'psar_df', 'rvi_df',
            'ui_df', 'tsi_df', 'nvi_df', 'donchian_df', 'ha_df',
            'spk_df', 'st_df', 'veri_ath', 'df_adx',
            'aroon_res', 'rvi_raw', 'cmo_res', 'uo_res', 'trix_res',
            'kst_res', 'dpo_res', 'coppock', 'cexit', 'basis',
            'ui_res', 'nvi_series', 'rsi_res', 'wma_res', 'lrc_res',
            'knox_bull_points', 'knox_bear_points', 'gold_cross', 'death_cross'
        ]

        for var_name in df_list:
            try:
                if var_name in locals() and locals()[var_name] is not None:
                    if hasattr(locals()[var_name], 'close'):
                        locals()[var_name].close()
                    del locals()[var_name]
            except:
                pass

        fig_list = [
            'fig', 'fig_candle', 'fig_candle_volume', 'fig_bar',
            'fig_alan', 'fig_heikin', 'hollow_candle'
        ]

        for var_name in fig_list:
            try:
                if var_name in locals() and locals()[var_name] is not None:
                    locals()[var_name].close()
                    del locals()[var_name]
            except:
                pass

        list_list = [
            'x_ekseni', 'mum_open', 'mum_high', 'mum_low', 'mum_close',
            'volume_values', 'hacim_etiketleri', 'mum_genislikleri',
            'renkler', 'bear_vals', 'bull_vals', 'cho_vals',
            'st_vals', 'st_dirs', 'ha_open', 'ha_high', 'ha_low', 'ha_close',
            'aroon_up_vals', 'aroon_down_vals', 'cmo_vals', 'kst_vals',
            'tsi_vals', 'nvi_vals', 'dpo_vals', 'uo_vals', 'trix_vals'
        ]

        for var_name in list_list:
            try:
                if var_name in locals() and locals()[var_name] is not None:
                    del locals()[var_name]
            except:
                pass

        json_list = [
            'fig_line', 'candle_json', 'bar_json', 'fig_candle_volume_json',
            'heikin_json', 'alan_json', 'hollow_json'
        ]

        for var_name in json_list:
            try:
                if var_name in locals() and locals()[var_name] is not None:
                    del locals()[var_name]
            except:
                pass

        try:
            if 'ai_ozet_veri' in locals():
                del locals()['ai_ozet_veri']
        except:
            pass

        try:
            if 'ai_response' in locals():
                del locals()['ai_response']
        except:
            pass

        gc.collect()
        gc.collect(generation=2)


@app.route("/Coklu_Grafik_Giris")
def çoklu_grafikler():
    return render_template("coklugrafikler.html")

@app.route("/Coklu_Grafik_Sonuc",methods=['POST'])
def çoklu_grafikler_penceresi():
    try:
        sembol1 = request.form.get("hisse1").upper()
        sembol2 = request.form.get("hisse2").upper()
        period = request.form.get("period","1mo")
        interval = request.form.get("interval","1d")
        dil = request.form.get('dil')

        if zaman_dilimi_kontrol(interval,period):
            return "<h1>Hata: Mum Aralığı (Interval), periyot aralığından büyük veya periyot aralığına eşit olamaz!</h1>"
        df1 = yf.download(sembol1,period=period,interval=interval,progress=False,prepost=False)
        df2 = yf.download(sembol2,period=period,interval=interval,progress=False,prepost=False)

        if df1.empty or df2.empty:
            return ("Bir Veya İki Hisse Senedi Verisi Çekilemedi Lütfen Sembol Bilgilerini Kontrol Edin")

        for df in [df1, df2]:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)

        common_index = df1.index.intersection(df2.index)
        df1 = df1.loc[common_index]
        df2 = df2.loc[common_index]
        fiyat1 = df1["Close"].astype(float)
        fiyat2 = df2["Close"].astype(float)

        df1_değişim = df1['Close'].iloc[-1] - df1.iloc[0]
        df2_değişim = df2.iloc[-1] - df2.iloc[0]
        df1_yuzde = (df1_değişim / fiyat1.iloc[0]) * 100
        df2_yuzde = (df2_değişim / fiyat2.iloc[0]) * 100
        df1_baslangic_fiyat = float(df1["Close"].iloc[0])
        df1_son_fiyat = float(df1["Close"].iloc[-1])
        df2_baslangic_fiyat = float(df2["Close"].iloc[0])
        df2_son_fiyat = float(df2["Close"].iloc[-1])
        df1_yuzde_serisi = (fiyat1 / fiyat1.iloc[0] - 1) * 100
        df2_yuzde_serisi = (fiyat2 / fiyat2.iloc[0] - 1) * 100
        df1_son = float(fiyat1.iloc[-1])
        df1_ilk = float(fiyat1.iloc[0])

        df2_son = float(fiyat2.iloc[-1])
        df2_ilk = float(fiyat2.iloc[0])
        df1_yüzde = ((df1_son - df1_ilk) / df1_ilk) * 100
        df2_yüzde = ((df2_son - df2_ilk) / df2_ilk) * 100
        x_ekseni = df1.index.strftime('%d.%m.%y %H:%M' if "m" in interval else '%d.%m.%y').tolist()
        fig = go.Figure()


        fig.add_trace(go.Scatter(x=x_ekseni,y=df1_yuzde_serisi.values.flatten().tolist(),mode='lines',line=dict(color='#6366f1', width=3),name=f"{sembol1} (%)",hovertemplate='%{y:.2f}%'))
        fig.add_trace(go.Scatter(x=x_ekseni,y=df2_yuzde_serisi.values.flatten().tolist(),mode='lines',line=dict(color='#f43f5e', width=3),name=f"{sembol2} (%)",hovertemplate='%{y:.2f}%'))
        fig.update_layout(template='plotly_dark',paper_bgcolor="#0f172a",
            plot_bgcolor="#0f172a",hovermode='x unified',legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            margin=dict(l=20, r=20, t=50, b=20),
            xaxis=dict(
                showgrid=True, gridcolor='rgba(255,255,255,0.05)',
                type='category', nticks=10
            ),
            yaxis=dict(
                showgrid=True, gridcolor='rgba(255,255,255,0.05)',
                title="Getiri (%)", side="right", ticksuffix="%"
            )
        )
        karşılaştırma_json = json.dumps(fig,cls=PlotlyJSONEncoder)
        korelasyon = fiyat1.corr(fiyat2)
        vol1 = df1['Close'].pct_change().std() * 100
        vol1 = float(vol1)
        vol2 = df2['Close'].pct_change().std() * 100
        vol2 = float(vol2)

        ai_ozet_veri = {}

        try:
            ai_response = client.chat.completions.create(
                model="Qwen/Qwen2.5-72B-Instruct",
                messages=[
                    {
                        "role": "system",
                        "content": f"ÖNCELİKLE BU YORUMUN TAMAMINI {dil} Dilinde Yap Sen Profesyonel Bir Borsa Analistisin Verileri Tekrar Etmeden Kullanıcıya Bu iki hissenin fiyatlarının karşılaştırıldığı bu grafikten ve sana verilen bilgilerdne yola çıkarak aşırı detaylı analiz yap ve en sonunda kullanıcıya alınması mı mantıklı yoksa satılmasının mı mantıklı olduğunu söyle {ai_ozet_veri}"
                    },
                    {
                        "role": "user",
                        "content": f"ÖNCELİKLE BU YORUMUN TAMAMINI {dil} Dilinde Yap Bu Hisse Verilerini Profesyonelce Kullanıcıya Verileri Tekrar Etmeden (Örneğin Peg Rasyosu 2 demene gerek yok) bu verilerden yola çıkarak hissenin ve şirketin geleceği potansiyel forsatlar hakkında aşırı detaylı ve bunları çok detaylıca açıkladıktan sonra yazının en sonunda yorum yap: {ai_ozet_veri}"
                    }
                ],
                max_tokens=1800
            )
            ai_analiz_notu = ai_response.choices[0].message.content
        except:
            ai_analiz_notu = "Hata Bir Sorun Oluştu Yapay Zekadan Yanıt Alınamadı"



        return render_template("ikilianalizpaneli.html",
                               grafik=karşılaştırma_json,
                               hisse=f"{sembol1} vs {sembol2}",
                               sembol1=sembol1,
                               sembol2=sembol2,
                               df1_yuzde=df2_yuzde.iloc[-1],
                               df2_yuzde=df2_yuzde.iloc[-1],
                               df1_baslangic_fiyat=df1_baslangic_fiyat,
                               df1_son_fiyat=df1_son_fiyat,
                               df2_baslangic_fiyat=df2_baslangic_fiyat,
                               df2_son_fiyat=df2_son_fiyat,korelasyon=korelasyon)
    except KeyError as e:
        return f"<h1>📊 Veri Formatı Hatası</h1><p>Borsadan gelen verilerde beklenen veri alanı bulunamadı.</p>"
    except requests.exceptions.Timeout:
        return "<h1>⌛ Sunucu Yanıt Vermiyor</h1><p>Veri kaynağı (Yahoo Finance/Borsa) çok geç yanıt veriyor, lütfen tekrar deneyin.</p>"


    except (requests.exceptions.ConnectionError, ConnectionError):
        return "<h1>🌐 Bağlantı Hatası</h1><p>İnternet bağlantınızı kontrol edin veya veri sağlayıcısının erişilebilir olduğundan emin olun.</p>"

    except ZeroDivisionError:
        return "<h1>🧮 Matematiksel Hata</h1><p>Veri setindeki eksiklikler nedeniyle finansal rasyolar hesaplanamadı (Sıfıra bölme hatası).</p>"

    except pd.errors.EmptyDataError:
        return "<h1>📉 Veri Boş</h1><p>Arattığınız hisse/kripto için geçmiş fiyat verisi bulunamadı.</p>"

    except ccxt.ExchangeError:
        return "<h1>🏛️ Borsa API Hatası</h1><p>Kripto borsasından veri çekilirken borsa kaynaklı bir hata oluştu.</p>"

    except ccxt.AuthenticationError:
        return "<h1>🔑 Yetkilendirme Hatası</h1><p>Borsa API anahtarlarınız hatalı veya süresi dolmuş.</p>"

    except PermissionError:
        return "<h1>🔒 Erişim Yetkisi Yok</h1><p>Sistem dosyalarına veya veritabanına erişim izniniz bulunmuyor.</p>"

    except Exception as e:
        return f"<h1>🛠️ Beklenmedik Bir Hata</h1><p>Sistem yöneticisine iletilmek üzere kaydedildi. Hata</p>"
    finally:
        if df1 is not None:
            del df1
        if df2 is not None:
            del df2
        if fiyat1 is not None:
            del fiyat1
        if fiyat2 is not None:
            del fiyat2

        if fig is not None:
            del fig

        if x_ekseni is not None:
            del x_ekseni

        if karşılaştırma_json is not None:
            del karşılaştırma_json

        gc.collect()
        gc.collect(generation=2)


@app.route("/Dolar_Bazlı_Grafik",methods=['POST','GET'])
def dolar_bazlı_grafik():
    p = session.get('last_period', '1mo')
    i = session.get('last_interval', '1d')
    s = session.get('last_sembol', '')
    d = session.get('last_exchange', 'Türkçe')
    return render_template("dolar_grafik.html",p=p,i=i,s=s,d=d)


@app.route("/Dolar_Bazlı_Grafik_Ekranı", methods=['POST'])
def dolar_bazlı_grafik_ekranı():
    try:
        sembol = request.form.get("hisse").upper()
        period = request.form.get("period")
        interval = request.form.get("interval")
        dovız_tipi = request.form.get("kur_tipi")
        session['last_period'] = period
        session['last_interval'] = interval
        session['last_sembol'] = sembol
        session['last_exchange'] = dovız_tipi

        p = session.get('last_period', '1mo')
        i = session.get('last_interval', '1d')
        s = session.get('last_sembol', '')
        d = session.get('last_exchange', 'Türkçe')

        if zaman_dilimi_kontrol(interval,period):
            return "<h1>Hata: Mum Aralığı (Interval), periyot aralığından büyük veya periyot aralığına eşit olamaz!</h1>"
        sembol_df = yf.download(sembol, period=period, interval=interval, progress=False,auto_adjust=True,prepost=False)
        usd_df = yf.download(dovız_tipi, period=period, interval=interval, progress=False,prepost=False)
        veri = yf.Ticker(sembol)
        data = veri.info
        long_name = data.get('longName')
        ilk_uc = dovız_tipi[:4]

        if sembol_df.empty:
            return "Hisse Senedi Alananı boş Bırakılamaz"

        if isinstance(sembol_df.columns, pd.MultiIndex):
            sembol_df.columns = sembol_df.columns.get_level_values(0)
        if isinstance(usd_df.columns, pd.MultiIndex):
            usd_df.columns = usd_df.columns.get_level_values(0)

        hisse = sembol_df
        dolar = usd_df

        ortak_tarihler = sembol_df.index.intersection(usd_df.index)
        if len(ortak_tarihler) == 0:
            return "Seçilen periyotta hisse ve kur verileri çakışmıyor. Lütfen daha geniş bir periyot seçin."

        if dovız_tipi in ["GC=F", "PA=F", "SI=F","BZ=F","CL=F"]:
            kur_df = yf.download("USDTRY=X", period=period, interval=interval, progress=False,prepost=False)
            if isinstance(kur_df.columns, pd.MultiIndex):
                kur_df.columns = kur_df.columns.get_level_values(0)

            ortak_tarihler = sembol_df.index.intersection(usd_df.index).intersection(kur_df.index)
            hisse_usd = sembol_df.loc[ortak_tarihler, "Close"] / kur_df.loc[ortak_tarihler, "Close"]
            dolar_bazlı_seri = (sembol_df.loc[ortak_tarihler, "Close"] / kur_df.loc[ortak_tarihler, "Close"]) / \
                               usd_df.loc[ortak_tarihler, "Close"]
        else:
            kur_df = yf.download(dovız_tipi,period=period,interval=interval,progress=False,prepost=False)
            ortak = sembol_df.index.intersection(usd_df.index)
            dolar_bazlı_seri = sembol_df.loc[ortak, "Close"] / usd_df.loc[ortak, "Close"]


        dolar_bazlı_seri = dolar_bazlı_seri.dropna()
        en_yüksek = float(dolar_bazlı_seri.max())
        en_düşük = float(dolar_bazlı_seri.min())

        ilk_fiyat = float(dolar_bazlı_seri.iloc[0])
        son_fiyat = float(dolar_bazlı_seri.iloc[-1])


        değişim = son_fiyat - ilk_fiyat
        toplam_degisim_yuzde = ((son_fiyat - ilk_fiyat) / ilk_fiyat) * 100

        if değişim < 0:
            renk = "red"
        elif değişim > 0:
            renk = "green"
        else:
            renk = "gray"

        x_ekseni = dolar_bazlı_seri.index.tz_localize(None).strftime('%d.%m.%y %H:%M' if 'm' in interval else '%d.%m.%y').tolist()
        y_ekseni = dolar_bazlı_seri.values.flatten().tolist()
        ohlc = ['Open', 'High', 'Low', 'Close']
        df_bazlı = pd.DataFrame(index=ortak_tarihler)
        for col in ohlc:
            df_bazlı[col] = sembol_df.loc[ortak_tarihler,col] / usd_df.loc[ortak_tarihler,'Close']



        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=x_ekseni,
            y=y_ekseni,
            mode="lines",
            line=dict(color=renk,width=3),
            fill='tozeroy',
            name=f"{sembol}",
        ))

        fig.add_hline(y=en_yüksek,line_color="green",line_dash='dash',opacity=0.3)
        fig.add_hline(y=en_düşük,line_color="red",line_dash='dash',opacity=0.3)
        fig.update_layout(
            template='plotly_dark',
            paper_bgcolor="#020617",
            plot_bgcolor="#020617",
            xaxis=dict(type='category', nticks=12, gridcolor="rgba(255,255,255,0.05)"),
            yaxis=dict(side="right", gridcolor="rgba(255,255,255,0.05)", tickformat=".4f"),
            margin=dict(l=10, r=10, t=10, b=40),
            hovermode='x unified',
            hoverlabel=dict(
                bgcolor="#020617",
                bordercolor="#1e293b"
            )
        )
        fig_candle = go.Figure()
        fig_candle.add_trace(go.Candlestick(x=x_ekseni,open=df_bazlı['Open'].values.flatten().tolist(),
        close=df_bazlı['Close'].tolist(),high=df_bazlı['High'].tolist(),low=df_bazlı['Low'].tolist(),increasing_line_color='#00ffbb',
        decreasing_line_color='#ff4b5c',
        name=f"{sembol} / {dovız_tipi}"))
        fig_candle.add_hline(y=en_yüksek,line_color='green',line_dash='dash',opacity=0.3)
        fig_candle.add_hline(y=en_düşük,line_color='red',line_dash='dash',opacity=0.3)
        fig_candle.update_layout(
            template='plotly_dark',
            paper_bgcolor="#020617",
            plot_bgcolor="#020617",
            xaxis=dict(nticks=12, rangeslider_visible=False),
            yaxis=dict(side="right", tickformat=".4f"),
            margin=dict(l=10, r=10, t=10, b=40),
            hovermode='x unified',
            hoverlabel=dict(
                bgcolor="#020617",
                font_size=12,
                font_family="Fira Code",
                bordercolor="#1e293b"
            )
        )



        grafik_json = json.dumps(fig, cls=PlotlyJSONEncoder)
        grafik_mum_json = json.dumps(fig_candle,cls=PlotlyJSONEncoder)

        del fig
        del fig_candle



        return render_template("Dolar_Bazlı_Grafik.html",
                               grafik_mum_json=grafik_mum_json,
                               long_name = long_name,
                               grafik=grafik_json,
                               sembol=sembol,
                               son_fiyat=round(son_fiyat, 2),
                               toplam_degisim_yuzde=round(toplam_degisim_yuzde, 2),
                               değişim=round(değişim, 2), period=period, interval=interval)
    except KeyError as e:
        return f"<h1>📊 Veri Formatı Hatası</h1><p>Borsadan gelen verilerde beklenen veri' alanı bulunamadı.</p>"
    except requests.exceptions.Timeout:
        return "<h1>⌛ Sunucu Yanıt Vermiyor</h1><p>Veri kaynağı (Yahoo Finance/Borsa) çok geç yanıt veriyor, lütfen tekrar deneyin.</p>"


    except (requests.exceptions.ConnectionError, ConnectionError):
        return "<h1>🌐 Bağlantı Hatası</h1><p>İnternet bağlantınızı kontrol edin veya veri sağlayıcısının erişilebilir olduğundan emin olun.</p>"

    except ZeroDivisionError:
        return "<h1>🧮 Matematiksel Hata</h1><p>Veri setindeki eksiklikler nedeniyle finansal rasyolar hesaplanamadı (Sıfıra bölme hatası).</p>"

    except pd.errors.EmptyDataError:
        return "<h1>📉 Veri Boş</h1><p>Arattığınız hisse/kripto için geçmiş fiyat verisi bulunamadı.</p>"

    except ccxt.ExchangeError:
        return "<h1>🏛️ Borsa API Hatası</h1><p>Kripto borsasından veri çekilirken borsa kaynaklı bir hata oluştu.</p>"

    except ccxt.AuthenticationError:
        return "<h1>🔑 Yetkilendirme Hatası</h1><p>Borsa API anahtarlarınız hatalı veya süresi dolmuş.</p>"

    except PermissionError:
        return "<h1>🔒 Erişim Yetkisi Yok</h1><p>Sistem dosyalarına veya veritabanına erişim izniniz bulunmuyor.</p>"

    except Exception as e:
        return f"<h1>🛠️ Beklenmedik Bir Hata</h1><p>Sistem yöneticisine iletilmek üzere kaydedildi./p>"
    finally:
        if sembol_df is not None:
            del sembol_df
        if usd_df is not None:
            del usd_df
        if veri is not None:
            del veri
        if data is not None:
            del data
        if dolar_bazlı_seri is not None:
            del dolar_bazlı_seri
        if df_bazlı is not None:
            del df_bazlı

        if x_ekseni is not None:
            del x_ekseni
        if y_ekseni is not None:
            del y_ekseni
        if grafik_json is not None:
            del grafik_json
        if grafik_mum_json is not None:
            del grafik_mum_json
        gc.collect()
        gc.collect(generation=2)





@app.route("/USD_HACİM")
def usd_hacim():
    return render_template("usd_hacim.html")

@app.route("/USD_HACİM_ANALİZ_BİLGİ",methods=['POST'])
def usd_hacim_analiz():
    try:
        sembol = request.form.get("hisse").upper()
        period = request.form.get("period")
        interval = request.form.get("interval")
        doviz_tipi = request.form.get('doviz_tipi').upper()

        if zaman_dilimi_kontrol(interval,period):
            return "<h1>Hata: Mum Aralığı (Interval), periyot aralığından büyük veya periyot aralığına eşit olamaz!</h1>"

        df = yf.download(sembol, period=period, interval=interval, progress=False,prepost=False)
        usd_df = yf.download(doviz_tipi, period=period, interval=interval, progress=False,prepost=False)
        if df.empty:
            return "<h1>Hisse Senedi Verisi Çekilemedi</h1>"
        if usd_df.empty:
            return "<h1>Döviz Verisi Çekilemedi </h1>"
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if isinstance(usd_df.columns, pd.MultiIndex):
            usd_df.columns = usd_df.columns.get_level_values(0)

        df = df.loc[:, ~df.columns.duplicated()]
        usd_df = usd_df.loc[:, ~usd_df.columns.duplicated()]

        common_dates = df.index.intersection(usd_df.index)
        if len(common_dates) == 0:
            return "<h1>Hisse Ve Döviz Verileri Çakışmıyor"
        df = df.loc[common_dates]
        usd_df = usd_df.loc[common_dates]

        df["USD_CLOSE"] = df["Close"] / usd_df["Close"]
        df["USD_VOLUME"] = (df["Close"] * df["Volume"] / usd_df['Close'])

        usd_hacim_serisi = df["USD_VOLUME"]
        son_usd_hacim = df["USD_VOLUME"].iloc[-1]
        ortalama_usd_hacim = float(df["USD_VOLUME"].mean())
        usd_hacim_fark_yuzde = ((son_usd_hacim - ortalama_usd_hacim) / ortalama_usd_hacim) * 100
        tarih = df.index
        ilk_usd_hacim = df["USD_VOLUME"].iloc[0]
        en_yüksek_hacim = float(usd_hacim_serisi.max())
        en_yüksek_tarih = usd_hacim_serisi.idxmax().strftime("%Y.%m.%d")
        en_düşük_hacim = float(usd_hacim_serisi.min())
        en_düşük_tarih = usd_hacim_serisi.idxmin().strftime("%Y.%m.%d")
        renk = "#00ffbb" if son_usd_hacim >= ilk_usd_hacim else "#ff4b5c"
        x_ekseni = df.index.strftime('%Y-%m-%d %H:%M').tolist()
        y_ekseni = df['USD_VOLUME'].values.tolist()


        değişim = son_usd_hacim - ilk_usd_hacim

        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=x_ekseni,
            y=y_ekseni,
            mode="lines",
            line=dict(color="#00ffbb", width=2),
            name=f"{sembol} HACİM-ZAMAN GRAFİĞİ"
        ))

        fig.add_hline(y=en_yüksek_hacim, line_color='green', line_dash='dash', opacity=0.3)
        fig.add_hline(y=en_düşük_hacim,line_color='red',line_dash='dash',opacity=0.3)

        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="#020617",
            plot_bgcolor="#020617",
            hovermode="x unified",
            xaxis=dict(
                type='date',
                tickangle=-45,
                nticks=15,
                title="Zaman",
                gridcolor="rgba(255,255,255,0.05)"
            ),
            yaxis=dict(
                title="Fiyat",
                side="right",
                gridcolor="rgba(255,255,255,0.05)"
            ),
            margin=dict(l=40, r=40, t=30, b=40),
            hoverlabel=dict(
                bgcolor="#020617",
                bordercolor="#1e293b",
                font_color="#e2e8f0",
                font_family="Fira Code"
            )
        )

        usd_hacim_json = json.dumps(fig,cls=PlotlyJSONEncoder)
        del fig
        return render_template("usd_hacim_sonuc.html",
                               usd_hacim_grafik_url=usd_hacim_json ,
                               sembol=sembol,
                               son_usd_hacim=son_usd_hacim,
                               usd_hacim_fark_yuzde=usd_hacim_fark_yuzde, en_yüksek_hacim=en_yüksek_hacim,
                               en_düşük_hacim=en_düşük_hacim, en_düşük_tarih=en_düşük_tarih,
                               en_yüksek_tarih=en_yüksek_tarih)

    except KeyError as e:
        return f"<h1>📊 Veri Formatı Hatası</h1><p>Borsadan gelen verilerde beklenen veri alanı bulunamadı.</p>"
    except requests.exceptions.Timeout:
        return "<h1>⌛ Sunucu Yanıt Vermiyor</h1><p>Veri kaynağı (Yahoo Finance/Borsa) çok geç yanıt veriyor, lütfen tekrar deneyin.</p>"


    except (requests.exceptions.ConnectionError, ConnectionError):
        return "<h1>🌐 Bağlantı Hatası</h1><p>İnternet bağlantınızı kontrol edin veya veri sağlayıcısının erişilebilir olduğundan emin olun.</p>"

    except ZeroDivisionError:
        return "<h1>🧮 Matematiksel Hata</h1><p>Veri setindeki eksiklikler nedeniyle finansal rasyolar hesaplanamadı (Sıfıra bölme hatası).</p>"

    except pd.errors.EmptyDataError:
        return "<h1>📉 Veri Boş</h1><p>Arattığınız hisse/kripto için geçmiş fiyat verisi bulunamadı.</p>"

    except ccxt.ExchangeError:
        return "<h1>🏛️ Borsa API Hatası</h1><p>Kripto borsasından veri çekilirken borsa kaynaklı bir hata oluştu.</p>"

    except ccxt.AuthenticationError:
        return "<h1>🔑 Yetkilendirme Hatası</h1><p>Borsa API anahtarlarınız hatalı veya süresi dolmuş.</p>"

    except PermissionError:
        return "<h1>🔒 Erişim Yetkisi Yok</h1><p>Sistem dosyalarına veya veritabanına erişim izniniz bulunmuyor.</p>"

    except Exception as e:
        return f"<h1>🛠️ Beklenmedik Bir Hata</h1><p>Sistem yöneticisine iletilmek üzere kaydedildi./p>"
    finally:
        del df
        del usd_df
        del usd_hacim_json
        gc.collect()




@app.route("/Coinler_Paneli")
@cache.cached(timeout=150)
def coinler_en_popüler():
    try:
        semboller = [
            "BTC-USD", "ETH-USD", "ETH-EUR","ETH-GBP","PAXG-USD","BNB-USD", "SOL-USD","STETH-USD", "XRP-USD", "ADA-USD",
            "AVAX-USD", "DOGE-USD", "DOT-USD", "LINK-USD", "LTC-USD","WTRX-USD","WBETH-USD","XMR-USD",
            "SHIB-USD", "TRX-USD", "ATOM-USD", "ETC-USD", "XLM-USD","HYPE32196-USD","ZEC-USD","HBAR-USD","CRO-USD",
            "ALGO-USD",  "FIL-USD", "APE-USD", "SAND-USD", "MANA-USD","SUSDE-USD","RAIN38341-USD","MNT27075-USD",
            "EGLD-USD", "AAVE-USD", "HBAR-USD","THETA-USD","FLOKI-USD","OKB-USD","JITOSOL-USD","ASTER36341-USD",
            "LDO-USD" , "ICP-USD", "RUNE-USD" , "AGIX-USD" , "SEI-USD" ,"KAS-USD","MKR-USD","PEPE24478-USD",
            "BTC-EUR","BTC-GBP",
            "KCS-USD","RENDER-USD","TRUMP35336-USD" , "FBTC-USD" ,"QNT-USD","SLISBNBX-USD"
        ]
        df = yf.download(semboller,period="1d",interval="1m",progress=False,threads=5,timeout=12,prepost=False)
        if df.empty:
            return "Veri Alınamadı"

        if 'Close' in df.columns:
            fiyatlar = df['Close']
        else:
            fiyatlar = df



        coin_listesi = []
        for sembol in fiyatlar.columns:
            seri = fiyatlar[sembol].dropna()
            ilk_fiyat = seri.iloc[0]
            son_fiyat = seri.iloc[-1]
            değişim = ((son_fiyat - ilk_fiyat) / ilk_fiyat) * 100
            data = yf.Ticker(sembol)
            market_değeri = data.info.get('MarketCap',0)


            if son_fiyat > 0.1:
                basamak = 3
            elif son_fiyat <0.1:
                basamak = 10
            elif son_fiyat <0.01:
                basamak = 20
            coin_listesi.append({'name' : sembol , 'price' : float(round(son_fiyat,basamak)) , 'degisim' : float(round(değişim,2))})
        coin_listesi.sort(key=lambda x: x['price'],reverse=True)
        return render_template("kripto_menu.html",veriler=coin_listesi)
    except KeyError as e:
        return f"<h1>📊 Veri Formatı Hatası</h1><p>Borsadan gelen verilerde beklenen veri alanı bulunamadı.</p>"
    except requests.exceptions.Timeout:
        return "<h1>⌛ Sunucu Yanıt Vermiyor</h1><p>Veri kaynağı (Yahoo Finance/Borsa) çok geç yanıt veriyor, lütfen tekrar deneyin.</p>"


    except (requests.exceptions.ConnectionError, ConnectionError):
        return "<h1>🌐 Bağlantı Hatası</h1><p>İnternet bağlantınızı kontrol edin veya veri sağlayıcısının erişilebilir olduğundan emin olun.</p>"

    except ZeroDivisionError:
        return "<h1>🧮 Matematiksel Hata</h1><p>Veri setindeki eksiklikler nedeniyle finansal rasyolar hesaplanamadı (Sıfıra bölme hatası).</p>"

    except pd.errors.EmptyDataError:
        return "<h1>📉 Veri Boş</h1><p>Arattığınız hisse/kripto için geçmiş fiyat verisi bulunamadı.</p>"

    except ccxt.ExchangeError:
        return "<h1>🏛️ Borsa API Hatası</h1><p>Kripto borsasından veri çekilirken borsa kaynaklı bir hata oluştu.</p>"

    except ccxt.AuthenticationError:
        return "<h1>🔑 Yetkilendirme Hatası</h1><p>Borsa API anahtarlarınız hatalı veya süresi dolmuş.</p>"

    except PermissionError:
        return "<h1>🔒 Erişim Yetkisi Yok</h1><p>Sistem dosyalarına veya veritabanına erişim izniniz bulunmuyor.</p>"

    except Exception as e:
        return f"<h1>🛠️ Beklenmedik Bir Hata</h1><p>Sistem yöneticisine iletilmek üzere kaydedildi./p>"
    finally:
        if df is not None:
            del df
        if fiyatlar is not None:
            del fiyatlar
        if coin_listesi is not None:
            del coin_listesi
        if data is not None:
            del data
        gc.collect()
        gc.collect(generation=2)


@app.route("/Borsa_Paneli")
@cache.cached(timeout=300)
def borsa_paneli():
    try:

        hisse_rehberi = {
            "XU100": {"ad": "BIST 100", "sektor": "Endeks"},
            "XU500": {"ad": "BIST 500", "sektor": "Endeks"},
            "XBANK": {"ad": "BIST Banka", "sektor": "Endeks"},
            "XTEKS": {"ad": "BIST Tekstil", "sektor": "Endeks"},
            "XELKT": {"ad": "BIST Elektrik", "sektor": "Endeks"},
            "XTCRT": {"ad": "BIST Ticaret", "sektor": "Endeks"},
            "XINSA": {"ad": "BIST İnşaat", "sektor": "Endeks"},
            "XTAST": {"ad": "BIST Taş Toprak", "sektor": "Endeks"},
            "XILTM": {"ad": "BIST İletişim", "sektor": "Endeks"},
            "XKAGT": {"ad": "BIST Kağıt", "sektor": "Endeks"},
            "XMANA": {"ad": "BIST Metal Ana", "sektor": "Endeks"},
            "XSPOR": {"ad": "BIST Spor", "sektor": "Endeks"},
            "XTMTU": {"ad": "BIST Temettü", "sektor": "Endeks"},
            "XUSIN": {"ad": "BIST Sınai", "sektor": "Endeks"},
            "XUTEK": {"ad": "BIST Teknoloji", "sektor": "Endeks"},
            "XHOLD": {"ad": "BIST Holding", "sektor": "Endeks"},
            "XGIDA": {"ad": "BIST Gıda", "sektor": "Endeks"},

            "AFYON": {"ad": "Afyon Çimento", "sektor": "Taş Toprak"},
            "AKCNS": {"ad": "Akçansa Çimento", "sektor": "Taş Toprak"},
            "BSOKE": {"ad": "Batısöke Çimento", "sektor": "Taş Toprak"},
            "BTCIM": {"ad": "Batıçim Çimento", "sektor": "Taş Toprak"},
            "BUCIM": {"ad": "Bursa Çimento", "sektor": "Taş Toprak"},
            "CIMSA": {"ad": "Çimsa Çimento", "sektor": "Taş Toprak"},
            "CMBTN": {"ad": "Çimbeton", "sektor": "Taş Toprak"},
            "DOGUB": {"ad": "Doğusan Boru", "sektor": "Taş Toprak"},
            "EGSER": {"ad": "Ege Seramik", "sektor": "Taş Toprak"},
            "GOLTS": {"ad": "Göltaş Çimento", "sektor": "Taş Toprak"},
            "KONYA": {"ad": "Konya Çimento", "sektor": "Taş Toprak"},
            "KUTPO": {"ad": "Kütahya Porselen", "sektor": "Taş Toprak"},
            "OYAKC": {"ad": "Oyak Çimento", "sektor": "Taş Toprak"},
            "NUHCM": {"ad": "Nuh Çimento", "sektor": "Taş Toprak"},
            "USAK": {"ad": "Uşak Seramik", "sektor": "Taş Toprak"},
            "NIBAS": {"ad": "Niğbaş Beton", "sektor": "Taş Toprak"},
            "KLKIM": {"ad": "Kalekim", "sektor": "Taş Toprak"},
            "BOBET": {"ad": "Boğaziçi Beton", "sektor": "Taş Toprak"},
            "BIENY": {"ad": "Bien Yapı Ürünleri", "sektor": "Taş Toprak"},
            "KLSER": {"ad": "Kaleseramik", "sektor": "Taş Toprak"},
            "TUREX": {"ad": "Tureks Madencilik", "sektor": "Taş Toprak"},
            "LMKDC": {"ad": "Limak Doğu Anadolu", "sektor": "Taş Toprak"},
            "CMENT": {"ad": "Çimentaş", "sektor": "Taş Toprak"},
            "SRVGY": {"ad": "Seranit (Servet GYO bünyesinde)", "sektor": "Taş Toprak"},
            "AKBNK": {"ad": "Akbank", "sektor": "Banka"},
            "GARAN": {"ad": "Garanti BBVA", "sektor": "Banka"},
            "ISCTR": {"ad": "İş Bankası (C)", "sektor": "Banka"},
            "HALKB": {"ad": "Halkbank", "sektor": "Banka"},
            "VAKBN": {"ad": "Vakıfbank", "sektor": "Banka"},
            "YKBNK": {"ad": "Yapı Kredi", "sektor": "Banka"},
            "TSKB": {"ad": "T.S.K.B.", "sektor": "Banka"},
            "SKBNK": {"ad": "Şekerbank", "sektor": "Banka"},
            "ALBRK": {"ad": "Albaraka Türk", "sektor": "Banka"},

            "AKENR": {"ad": "Akenerji", "sektor": "Enerji"},
            "AKSEN": {"ad": "Aksa Enerji", "sektor": "Enerji"},
            "AKSUE": {"ad": "Aksu Enerji", "sektor": "Enerji"},
            "AYEN": {"ad": "Ayen Enerji", "sektor": "Enerji"},
            "ZEDUR": {"ad": "Zedur Enerji", "sektor": "Enerji"},
            "ZOREN": {"ad": "Zorlu Enerji", "sektor": "Enerji"},
            "LYDYE": {"ad": "Lydia Yeşil Enerji", "sektor": "Enerji"},
            "ODAS": {"ad": "ODAŞ Elektrik", "sektor": "Enerji"},
            "PAMEL": {"ad": "Pamukova Yenilenebilir Enerji", "sektor": "Enerji"},
            "ENJSA": {"ad": "Enerjisa Enerji", "sektor": "Enerji"},
            "NATEN": {"ad": "Naturel Yenilenebilir Enerji", "sektor": "Enerji"},
            "ESEN": {"ad": "Esenboğa Elektrik", "sektor": "Enerji"},
            "NTGAZ": {"ad": "Naturelgaz", "sektor": "Enerji"},
            "GWIND": {"ad": "Galata Wind Enerji", "sektor": "Enerji"},
            "BIOEN": {"ad": "Biotrend Yatırım", "sektor": "Enerji"},
            "AYDEM": {"ad": "Aydem Enerji", "sektor": "Enerji"},
            "CANTE": {"ad": "Can2 Termik", "sektor": "Enerji"},
            "MAGEN": {"ad": "Margün Enerji", "sektor": "Enerji"},
            "ARASE": {"ad": "Doğu Aras Enerji", "sektor": "Enerji"},
            "HUNER": {"ad": "Hun Yenilenebilir Enerji", "sektor": "Enerji"},
            "SMRTG": {"ad": "Smart Güneş Enerjisi", "sektor": "Enerji"},
            "CONSE": {"ad": "Consus Enerji", "sektor": "Enerji"},
            "ALFAS": {"ad": "Alfa Solar Enerji", "sektor": "Enerji"},
            "AHGAZ": {"ad": "Ahlatcı Doğal Gaz", "sektor": "Enerji"},
            "AKFYE": {"ad": "Akfen Yenilenebilir Enerji", "sektor": "Enerji"},
            "CWENE": {"ad": "Cw Enerji", "sektor": "Enerji"},
            "IZENR": {"ad": "İzdemir Enerji", "sektor": "Enerji"},
            "TATEN": {"ad": "Tatlıpınar Enerji", "sektor": "Enerji"},
            "ENERY": {"ad": "Enerya Enerji", "sektor": "Enerji"},
            "CATES": {"ad": "Çates Elektrik", "sektor": "Enerji"},
            "MOGAN": {"ad": "Mogan Enerji", "sektor": "Enerji"},
            "ENTRA": {"ad": "Ic Enterra", "sektor": "Enerji"},
            "BIGEN": {"ad": "Birleşim Grup Enerji", "sektor": "Enerji"},
            "ENDAE": {"ad": "Enda Enerji Holding", "sektor": "Enerji"},
            "KLYPV": {"ad": "Kalyon Güneş Teknolojileri", "sektor": "Enerji"},
            "A1YEN": {"ad": "A1 Yenilenebilir Enerji", "sektor": "Enerji"},
            "ECOGR": {"ad": "Ecogreen Enerji", "sektor": "Enerji"},
            "ARFYE": {"ad": "Arf Bio Yenilenebilir", "sektor": "Enerji"},
            "ASTOR" : {'ad' : "Astor Enerji A.Ş.","sektor":"Enerji"},

            "THYAO": {"ad": "Türk Hava Yolları", "sektor": "Ulaşım"},
            "PGSUS": {"ad": "Pegasus", "sektor": "Ulaşım"},
            "TAVHL": {"ad": "TAV Havalimanları", "sektor": "Ulaşım"},
            "DOAS": {"ad": "Doğuş Otomotiv", "sektor": "Ulaşım"},
            "FROTO": {"ad": "Ford Otosan", "sektor": "Ulaşım"},
            "TOASO": {"ad": "Tofaş Oto", "sektor": "Ulaşım"},
            "CLEBI": {"ad": "Çelebi Hava Servisi", "sektor": "Ulaşım"},
            "GSDDE": {"ad": "GSD Marin", "sektor": "Ulaşım"},
            "RYSAS": {"ad": "Reysaş Taşımacılık", "sektor": "Ulaşım"},
            "BEYAZ": {"ad": "Beyaz Filo Oto Kiralama", "sektor": "Ulaşım"},
            "PGSUS": {"ad": "Pegasus Hava Taşımacılığı", "sektor": "Ulaşım"},
            "TLMAN": {"ad": "Trabzon Liman İşletmeciliği", "sektor": "Ulaşım"},
            "TUREX": {"ad": "Tureks Turizm", "sektor": "Ulaşım"},
            "GRSEL": {"ad": "Gür-Sel Turizm Taşımacılık", "sektor": "Ulaşım"},
            "PASEU": {"ad": "Pasifik Eurasia Lojistik", "sektor": "Ulaşım"},
            "HRKET": {"ad": "Hareket Proje Taşımacılığı", "sektor": "Ulaşım"},
            "HOROZ": {"ad": "Horoz Lojistik", "sektor": "Ulaşım"},
            #SINAI VE ÜRETİM
            "ADEL": {"ad": "Adel Kalemcilik", "sektor": "Sınai"},
            "AEFES": {"ad": "Anadolu Efes", "sektor": "Sınai"},
            "AKSA": {"ad": "Aksa Akrilik", "sektor": "Sınai"},
            "ALCAR": {"ad": "Alarko Carrier", "sektor": "Sınai"},
            "ALKA": {"ad": "Alkim Kağıt", "sektor": "Sınai"},
            "ALKIM": {"ad": "Alkim Kimya", "sektor": "Sınai"},
            "ARCLK": {"ad": "Arçelik A.Ş.", "sektor": "Sınai"},
            "ARSAN": {"ad": "Arsan Tekstil", "sektor": "Sınai"},
            "ASUZU": {"ad": "Anadolu Isuzu", "sektor": "Sınai"},
            "AVOD": {"ad": "AVOD Gıda", "sektor": "Sınai"},
            "AYGAZ": {"ad": "Aygaz A.Ş.", "sektor": "Sınai"},
            "BAGFS": {"ad": "Bağfaş Gübre", "sektor": "Sınai"},
            "BAKAB": {"ad": "Bak Ambalaj", "sektor": "Sınai"},
            "BANVT": {"ad": "Banvit", "sektor": "Sınai"},
            "BLCYT": {"ad": "Bilici Yatırım", "sektor": "Sınai"},
            "BOSSA": {"ad": "Bossa Tekstil", "sektor": "Sınai"},
            "BRKSN": {"ad": "Berkosan", "sektor": "Sınai"},
            "BRISA": {"ad": "Borusan Birleşik", "sektor": "Sınai"},
            "BURCE": {"ad": "Burçelik Çelik", "sektor": "Sınai"},
            "BURVA": {"ad": "Burçelik Vana", "sektor": "Sınai"},
            "CELHA": {"ad": "Çelik Halat", "sektor": "Sınai"},
            "CEMAS": {"ad": "Çemaş Döküm", "sektor": "Sınai"},
            "CEMTS": {"ad": "Çemtaş Çelik", "sektor": "Sınai"},
            "DOKTA": {"ad": "Döktaş Dökümcülük", "sektor": "Sınai"},
            "DAGI": {"ad": "Dagi Giyim", "sektor": "Sınai"},
            "DARDL": {"ad": "Dardanel Önentaş", "sektor": "Sınai"},
            "DERIM": {"ad": "Derimod", "sektor": "Sınai"},
            "DESA": {"ad": "Desa Deri", "sektor": "Sınai"},
            "DEVA": {"ad": "Deva Holding", "sektor": "Sınai"},
            "DITAS": {"ad": "Ditaş Doğan", "sektor": "Sınai"},
            "DMSAS": {"ad": "Demisaş Döküm", "sektor": "Sınai"},
            "DURDO": {"ad": "Duran Doğan Basım", "sektor": "Sınai"},
            "DYOBY": {"ad": "DYO Boya", "sektor": "Sınai"},
            "EGEEN": {"ad": "Ege Endüstri", "sektor": "Sınai"},
            "EGGUB": {"ad": "Ege Gübre", "sektor": "Sınai"},
            "EGPRO": {"ad": "Ege Profil", "sektor": "Sınai"},
            "EMKEL": {"ad": "EMEK Elektrik", "sektor": "Sınai"},
            "EPLAS": {"ad": "Egeplast", "sektor": "Sınai"},
            "ERBOS": {"ad": "Erbosan Boru", "sektor": "Sınai"},
            "EREGL": {"ad": "Erdemir", "sektor": "Sınai"},
            "ERSU": {"ad": "ERSU Meyve", "sektor": "Sınai"},
            "FMIZP": {"ad": "Federal Mogul", "sektor": "Sınai"},
            "FRIGO": {"ad": "Frigo Pak Gıda", "sektor": "Sınai"},
            "FROTO": {"ad": "Ford Otomotiv", "sektor": "Sınai"},
            "GENTS": {"ad": "Gentaş", "sektor": "Sınai"},
            "GEREL": {"ad": "Gersan Elektrik", "sektor": "Sınai"},
            "GOODY": {"ad": "Goodyear", "sektor": "Sınai"},
            "GUBRF": {"ad": "Gübretaş", "sektor": "Sınai"},
            "HATEK": {"ad": "Hateks Tekstil", "sektor": "Sınai"},
            "HEKTS": {"ad": "Hektaş Ticaret", "sektor": "Sınai"},
            "IHEVA": {"ad": "İhlas Ev Aletleri", "sektor": "Sınai"},
            "IZMDC": {"ad": "İzmir Demir Çelik", "sektor": "Sınai"},
            "KAPLM": {"ad": "Kaplamin Ambalaj", "sektor": "Sınai"},
            "KARSN": {"ad": "Karsan Otomotiv", "sektor": "Sınai"},
            "KARTN": {"ad": "Kartonsan", "sektor": "Sınai"},
            "KATMR": {"ad": "Katmerciler", "sektor": "Sınai"},
            "KRSTL": {"ad": "Kristal Kola", "sektor": "Sınai"},
            "KRDMA": {"ad": "Kardemir A", "sektor": "Sınai"},
            "KORDS": {"ad": "Kordsa Teknik", "sektor": "Sınai"},
            "KLMSN": {"ad": "Klimasan Klima", "sektor": "Sınai"},
            "KNFRT": {"ad": "Konfrut Gıda", "sektor": "Sınai"},
            "KRTEK": {"ad": "Karsu Tekstil", "sektor": "Sınai"},
            "LUKSK": {"ad": "Lüks Kadife", "sektor": "Sınai"},
            "MRSHL": {"ad": "Marshall Boya", "sektor": "Sınai"},
            "MNDRS": {"ad": "Menderes Tekstil", "sektor": "Sınai"},
            "OTKAR": {"ad": "Otokar", "sektor": "Sınai"},
            "PARSN": {"ad": "Parsan Makina", "sektor": "Sınai"},
            "PENGD": {"ad": "Penguen Gıda", "sektor": "Sınai"},
            "PETKM": {"ad": "Petkim", "sektor": "Sınai"},
            "PETUN": {"ad": "Pınar Et ve Un", "sektor": "Sınai"},
            "PINSU": {"ad": "Pınar Su", "sektor": "Sınai"},
            "PNSUT": {"ad": "Pınar Süt", "sektor": "Sınai"},
            "PRKME": {"ad": "Park Elektrik", "sektor": "Sınai"},
            "PRKAB": {"ad": "Türk Prysmian", "sektor": "Sınai"},
            "SAMAT": {"ad": "Saray Matbaacılık", "sektor": "Sınai"},
            "SARKY": {"ad": "Sarkuysan Elektrolit", "sektor": "Sınai"},
            "SASA": {"ad": "SASA Polyester", "sektor": "Sınai"},
            "SILVR": {"ad": "Silverline Endüstri", "sektor": "Sınai"},
            "SKTAS": {"ad": "Söktaş Tekstil", "sektor": "Sınai"},
            "TBORG": {"ad": "Türk Tuborg", "sektor": "Sınai"},
            "TOASO": {"ad": "Tofaş", "sektor": "Sınai"},
            "TRCAS": {"ad": "Turcas Petrol", "sektor": "Sınai"},
            "TTRAK": {"ad": "Türk Traktör", "sektor": "Sınai"},
            "TUKAS": {"ad": "Tukaş Gıda", "sektor": "Sınai"},
            "TUPRS": {"ad": "Tüpraş", "sektor": "Sınai"},
            "ULKER": {"ad": "Ülker Bisküvi", "sektor": "Sınai"},
            "ACSEL": {"ad": "Acıselsan Acıpayam", "sektor": "Sınai"},
            "ADESE": {"ad": "Adese Gayrimenkul", "sektor": "Sınai"},
            "AFYON": {"ad": "Afyon Çimento", "sektor": "Taş Toprak"},
            "AKCNS": {"ad": "Akçansa Çimento", "sektor": "Taş Toprak"},
            "AKSA": {"ad": "Aksa Akrilik", "sektor": "Sınai"},
            "ALCAR": {"ad": "Alarko Carrier", "sektor": "Sınai"},
            "ALKA": {"ad": "Alkim Kağıt", "sektor": "Sınai"},
            "ALKIM": {"ad": "Alkim Kimya", "sektor": "Sınai"},
            "ARCLK": {"ad": "Arçelik", "sektor": "Sınai"},
            "ARSAN": {"ad": "Arsan Tekstil", "sektor": "Sınai"},
            "ASUZU": {"ad": "Anadolu Isuzu", "sektor": "Sınai"},
            "AVOD": {"ad": "Avod Gıda", "sektor": "Sınai"},
            "AYGAZ": {"ad": "Aygaz", "sektor": "Sınai"},
            "BAGFS": {"ad": "Bağfaş", "sektor": "Sınai"},
            "BAKAB": {"ad": "Bak Ambalaj", "sektor": "Sınai"},
            "BANVT": {"ad": "Banvit", "sektor": "Sınai"},
            "BNTAS": {"ad": "Bantaş", "sektor": "Sınai"},
            "BARMA": {"ad": "Barem Ambalaj", "sektor": "Sınai"},
            "BERA": {"ad": "Bera Holding", "sektor": "Holding"},
            "BRISA": {"ad": "Brisa", "sektor": "Sınai"},
            "BSOKE": {"ad": "Batısöke Çimento", "sektor": "Taş Toprak"},
            "BTCIM": {"ad": "Batıçim Çimento", "sektor": "Taş Toprak"},
            "BUCIM": {"ad": "Bursa Çimento", "sektor": "Taş Toprak"},
            "BURCE": {"ad": "Burçelik", "sektor": "Sınai"},
            "BURVA": {"ad": "Burçelik Vana", "sektor": "Sınai"},
            "CANTE": {"ad": "Çan2 Termik", "sektor": "Sınai"},
            "CELHA": {"ad": "Çelik Halat", "sektor": "Sınai"},
            "CEMAS": {"ad": "Çemaş Döküm", "sektor": "Sınai"},
            "CEMTS": {"ad": "Çemtaş", "sektor": "Sınai"},
            "CIMSA": {"ad": "Çimsa", "sektor": "Taş Toprak"},
            "CMBTN": {"ad": "Çimbeton", "sektor": "Taş Toprak"},
            "CMENT": {"ad": "Çimentaş", "sektor": "Taş Toprak"},
            "CONSE": {"ad": "Consus Enerji", "sektor": "Sınai"},
            "CUSAN": {"ad": "Çuhadaroğlu Metal", "sektor": "Sınai"},
            "DAGI": {"ad": "Dagi Giyim", "sektor": "Sınai"},
            "DARDL": {"ad": "Dardanel", "sektor": "Sınai"},
            "DERIM": {"ad": "Derimod", "sektor": "Sınai"},
            "DESA": {"ad": "Desa Deri", "sektor": "Sınai"},
            "DEVA": {"ad": "Deva Holding", "sektor": "Sınai"},
            "DITAS": {"ad": "Ditaş Doğan", "sektor": "Sınai"},
            "DMSAS": {"ad": "Demisaş Döküm", "sektor": "Sınai"},
            "DOKTA": {"ad": "Döktaş Döküm", "sektor": "Sınai"},
            "DURDO": {"ad": "Duran Doğan Basım", "sektor": "Sınai"},
            "DYOBY": {"ad": "Dyo Boya", "sektor": "Sınai"},
            "EGEEN": {"ad": "Ege Endüstri", "sektor": "Sınai"},
            "EGGUB": {"ad": "Ege Gübre", "sektor": "Sınai"},
            "EGPRO": {"ad": "Ege Profil", "sektor": "Sınai"},
            "EGSER": {"ad": "Ege Seramik", "sektor": "Taş Toprak"},
            "EMKEL": {"ad": "Emek Elektrik", "sektor": "Sınai"},
            "EPLAS": {"ad": "Egeplast", "sektor": "Sınai"},
            "ERBOS": {"ad": "Erbosan", "sektor": "Sınai"},
            "EREGL": {"ad": "Erdemir", "sektor": "Sınai"},
            "ERSU": {"ad": "Ersu Gıda", "sektor": "Sınai"},
            "ESCOM": {"ad": "Escort Teknoloji", "sektor": "Sınai"},
            "FMIZP": {"ad": "Federal Mogul İzmit", "sektor": "Sınai"},
            "FRIGO": {"ad": "Frigo Pak Gıda", "sektor": "Sınai"},
            "FROTO": {"ad": "Ford Otosan", "sektor": "Sınai"},
            "GEDZA": {"ad": "Gediz Ambalaj", "sektor": "Sınai"},
            "GENTS": {"ad": "Gentaş", "sektor": "Sınai"},
            "GEREL": {"ad": "Gersan Elektrik", "sektor": "Sınai"},
            "GOLTS": {"ad": "Göltaş Çimento", "sektor": "Taş Toprak"},
            "GOODY": {"ad": "Goodyear", "sektor": "Sınai"},
            "GUBRF": {"ad": "Gübretaş", "sektor": "Sınai"},
            "HATEK": {"ad": "Hateks", "sektor": "Sınai"},
            "HEKTS": {"ad": "Hektaş", "sektor": "Sınai"},
            "IHEVA": {"ad": "İhlas Ev Aletleri", "sektor": "Sınai"},
            "ISKPL": {"ad": "Işık Plastik", "sektor": "Sınai"},
            "ISDMR": {"ad": "İskenderun Demir Çelik", "sektor": "Sınai"},
            "IZMDC": {"ad": "İzmir Demir Çelik", "sektor": "Sınai"},
            "JANTS": {"ad": "Jantsa", "sektor": "Sınai"},
            "KAPLM": {"ad": "Kaplamin", "sektor": "Sınai"},
            "KAREL": {"ad": "Karel Elektronik", "sektor": "Sınai"},
            "KARSN": {"ad": "Karsan", "sektor": "Sınai"},
            "KARTN": {"ad": "Kartonsan", "sektor": "Sınai"},
            "KATMR": {"ad": "Katmerciler", "sektor": "Sınai"},
            "KFEIN": {"ad": "Kafein Yazılım", "sektor": "Sınai"},
            "KIMMR": {"ad": "Kiler Tekstil", "sektor": "Sınai"},
            "KLMSN": {"ad": "Klimasan", "sektor": "Sınai"},
            "KNFRT": {"ad": "Konfrut Gıda", "sektor": "Sınai"},
            "KONYA": {"ad": "Konya Çimento", "sektor": "Taş Toprak"},
            "KORDS": {"ad": "Kordsa", "sektor": "Sınai"},
            "KRTEK": {"ad": "Karsu Tekstil", "sektor": "Sınai"},
            "KRSTL": {"ad": "Kristal Kola", "sektor": "Sınai"},
            "KUTPO": {"ad": "Kütahya Porselen", "sektor": "Taş Toprak"},
            "LUKSK": {"ad": "Lüks Kadife", "sektor": "Sınai"},
            "MAKTK": {"ad": "Makina Takım", "sektor": "Sınai"},
            "BLUME": {"ad": "Metemtur", "sektor": "Sınai"},
            "MNDRS": {"ad": "Menderes Tekstil", "sektor": "Sınai"},
            "MRSHL": {"ad": "Marshall", "sektor": "Sınai"},
            "MSGYO": {"ad": "Mistral GYO", "sektor": "Sınai"},
            "NIBAS": {"ad": "Niğbaş Beton", "sektor": "Taş Toprak"},
            "NUHCM": {"ad": "Nuh Çimento", "sektor": "Taş Toprak"},
            "OTKAR": {"ad": "Otokar", "sektor": "Sınai"},
            "OYAKC": {"ad": "Oyak Çimento", "sektor": "Taş Toprak"},
            "OZKGY": {"ad": "Özak GYO", "sektor": "Sınai"},
            "PARSN": {"ad": "Parsan", "sektor": "Sınai"},
            "PENGD": {"ad": "Penguen Gıda", "sektor": "Sınai"},
            "PETKM": {"ad": "Petkim", "sektor": "Sınai"},
            "PETUN": {"ad": "Pınar Et Un", "sektor": "Sınai"},
            "PINSU": {"ad": "Pınar Su", "sektor": "Sınai"},
            "PNSUT": {"ad": "Pınar Süt", "sektor": "Sınai"},
            "POLTK": {"ad": "Politeknik Metal", "sektor": "Sınai"},
            "PRKAB": {"ad": "Prysmian Kablo", "sektor": "Sınai"},
            "PRKME": {"ad": "Park Elektrik", "sektor": "Sınai"},
            "PRZMA": {"ad": "Prizma Press", "sektor": "Sınai"},
            "SAMAT": {"ad": "Saray Matbaa", "sektor": "Sınai"},
            "SANEL": {"ad": "Sanel Mühendislik", "sektor": "Sınai"},
            "SANFM": {"ad": "Sanifoam", "sektor": "Sınai"},
            "SARKY": {"ad": "Sarkuysan", "sektor": "Sınai"},
            "SASA": {"ad": "Sasa", "sektor": "Sınai"},
            "SAYAS": {"ad": "Say Yenilenebilir", "sektor": "Sınai"},
            "SEKUR": {"ad": "Sekuro Plastik", "sektor": "Sınai"},
            "DUNYH": {"ad": "Selçuk Gıda", "sektor": "Sınai"},
            "SILVR": {"ad": "Silverline", "sektor": "Sınai"},
            "SKTAS": {"ad": "Söktaş", "sektor": "Sınai"},
            "SUNTK": {"ad": "Sun Tekstil", "sektor": "Sınai"},
            "TATGD": {"ad": "Tat Gıda", "sektor": "Sınai"},
            "TBORG": {"ad": "Türk Tuborg", "sektor": "Sınai"},
            "TEKTU": {"ad": "Tek-Art Turizm", "sektor": "Sınai"},
            "TMPOL": {"ad": "Temapol Polimer", "sektor": "Sınai"},
            "TMSN": {"ad": "Tümosan", "sektor": "Sınai"},
            "TOASO": {"ad": "Tofaş", "sektor": "Sınai"},
            "TRCAS": {"ad": "Turcas Petrol", "sektor": "Sınai"},
            "TRILC": {"ad": "Türk İlaç Serum", "sektor": "Sınai"},
            "TTRAK": {"ad": "Türk Traktör", "sektor": "Sınai"},
            "TUKAS": {"ad": "Tukaş", "sektor": "Sınai"},
            "TUPRS": {"ad": "Tüpraş", "sektor": "Sınai"},
            "UFUK": {"ad": "Ufuk Yatırım", "sektor": "Sınai"},
            "ULAS": {"ad": "Ulaşlar Turizm", "sektor": "Sınai"},
            "ULKER": {"ad": "Ülker", "sektor": "Sınai"},
            "USAK": {"ad": "Uşak Seramik", "sektor": "Taş Toprak"},
            "VANGD": {"ad": "Vanet Gıda", "sektor": "Sınai"},
            "VESBE": {"ad": "Vestel Beyaz Eşya", "sektor": "Sınai"},
            "VESTL": {"ad": "Vestel", "sektor": "Sınai"},
            "VKING": {"ad": "Viking Kağıt", "sektor": "Sınai"},
            "YAPRK": {"ad": "Yaprak Süt", "sektor": "Sınai"},
            "YATAS": {"ad": "Yataş", "sektor": "Sınai"},
            "YESIL": {"ad": "Yeşil Yatırım", "sektor": "Sınai"},
            "YUNSA": {"ad": "Yünsa", "sektor": "Sınai"},

            "AEFES": {"ad": "Anadolu Efes", "sektor": "Gıda"},
            "ALKLC": {"ad": "Altın Kılıç Gıda", "sektor": "Gıda"},
            "ARMGD": {"ad": "Arzum Ev Aletleri", "sektor": "Gıda"},
            "ATAKP": {"ad": "Atakey Patates", "sektor": "Gıda"},
            "AVOD": {"ad": "Avod Kurutulmuş Gıda", "sektor": "Gıda"},
            "BALSU": {"ad": "Balsu Gıda", "sektor": "Gıda"},
            "BANVT": {"ad": "Banvit", "sektor": "Gıda"},
            "BESLR": {"ad": "Besler Gıda", "sektor": "Gıda"},
            "BORSK": {"ad": "Bor Şeker", "sektor": "Gıda"},
            "CCOLA": {"ad": "Coca Cola İçecek", "sektor": "Gıda"},
            "CEMZY": {"ad": "Cem Zeytin", "sektor": "Gıda"},
            "DARDL": {"ad": "Dardanel", "sektor": "Gıda"},
            "DMRGD": {"ad": "Dmr Unlu Mamuller", "sektor": "Gıda"},
            "DURKN": {"ad": "Durukan Şekerleme", "sektor": "Gıda"},
            "EFOR": {"ad": "Efor Yatırım", "sektor": "Gıda"},
            "EKSUN": {"ad": "Eksun Gıda", "sektor": "Gıda"},
            "ERSU": {"ad": "Ersu Gıda", "sektor": "Gıda"},
            "FADE": {"ad": "Fade Gıda", "sektor": "Gıda"},
            "FRIGO": {"ad": "Frigo Pak Gıda", "sektor": "Gıda"},
            "GOKNR": {"ad": "Göknur Gıda", "sektor": "Gıda"},
            "GUNDG": {"ad": "Gündoğdu Gıda", "sektor": "Gıda"},
            "KAYSE": {"ad": "Kayseri Şeker", "sektor": "Gıda"},
            "KRSTL": {"ad": "Kristal Kola", "sektor": "Gıda"},
            "KRVGD": {"ad": "Kervan Gıda", "sektor": "Gıda"},
            "MERKO": {"ad": "Merko Gıda", "sektor": "Gıda"},
            "OBAMS": {"ad": "Oba Makarnacılık", "sektor": "Gıda"},
            "OFSYM": {"ad": "Ofis Yem Gıda", "sektor": "Gıda"},
            "OYLUM": {"ad": "Oylum Sınai Yatırımlar", "sektor": "Gıda"},
            "PENGD": {"ad": "Penguen Gıda", "sektor": "Gıda"},
            "PETUN": {"ad": "Pınar Et ve Un", "sektor": "Gıda"},
            "PINSU": {"ad": "Pınar Su", "sektor": "Gıda"},
            "PNSUT": {"ad": "Pınar Süt", "sektor": "Gıda"},
            "SEGMN": {"ad": "Segmen Kardeşler Gıda", "sektor": "Gıda"},
            "SOKE": {"ad": "Söke Değirmencilik", "sektor": "Gıda"},
            "TATGD": {"ad": "Tat Gıda", "sektor": "Gıda"},
            "TBORG": {"ad": "Türk Tuborg", "sektor": "Gıda"},
            "TUKAS": {"ad": "Tukaş", "sektor": "Gıda"},
            "ULKER": {"ad": "Ülker Bisküvi", "sektor": "Gıda"},
            "ULUUN": {"ad": "Ulusoy Un", "sektor": "Gıda"},
            "VANGD": {"ad": "Vanet Gıda", "sektor": "Gıda"},
            "YYLGD": {"ad": "Yayla Gıda", "sektor": "Gıda"},

            "ASELS": {"ad": "Aselsan", "sektor": "Savunma/Teknoloji"},
            "MIATK": {"ad": "Mia Teknoloji", "sektor": "Savunma/Teknoloji"},
            "REEDR": {"ad": "Reeder Teknoloji", "sektor": "Savunma/Teknoloji"},
            "SDTTR": {"ad": "SDT Savunma", "sektor": "Savunma/Teknoloji"},
            "KCHOL": {"ad": "Koç Holding", "sektor": "Holding"},
            "SAHOL": {"ad": "Sabancı Holding", "sektor": "Holding"},
            "AGHOL": {"ad": "AG Anadolu Grubu", "sektor": "Holding"},
            "DOHOL": {"ad": "Doğan Holding", "sektor": "Holding"},
            "TKFEN": {"ad": "Tekfen Holding", "sektor": "Holding"},
            "ALARK": {"ad": "Alarko Holding", "sektor": "Holding"},
            "GSDHO": {"ad": "GSD Holding", "sektor": "Holding"},
            "IHLAS": {"ad": "İhlas Holding", "sektor": "Holding"},
            "SISE": {"ad": "Şişecam", "sektor": "Holding"},
            "METRO": {"ad": "Metro Holding", "sektor": "Holding"},
            "VERUS": {"ad": "Verusa Holding", "sektor": "Holding"},
            "DERHL": {"ad": "Derluks Yatırım Hol.", "sektor": "Holding"},
            "HEDEF": {"ad": "Hedef Holding", "sektor": "Holding"},
            "POLHO": {"ad": "Polisan Holding", "sektor": "Holding"},
            "LYDHO": {"ad": "Lydia Holding", "sektor": "Holding"},


            # YATIRIM VE GİRİŞİM SERMAYESİ
            "BRYAT": {"ad": "Borusan Yatırım", "sektor": "Yatırım"},
            "ISMEN": {"ad": "İş Yatırım Menkul", "sektor": "Yatırım"},
            "INVEO": {"ad": "Inveo Yatırım", "sektor": "Yatırım"},
            "GLYHO": {"ad": "Global Yatırım Hol.", "sektor": "Yatırım"},
            "GOZDE": {"ad": "Gözde Girişim", "sektor": "Yatırım"},
            "ISGSY": {"ad": "İş Girişim", "sektor": "Yatırım"},
            "IDGYO": {"ad": "İdeal GYO / Yatırım", "sektor": "Yatırım"},
            "BERA": {"ad": "Bera Holding", "sektor": "Yatırım"},
            "HDFGS": {"ad": "Hedef Girişim", "sektor": "Yatırım"},
            "VERTU": {"ad": "Verusaturk Girişim", "sektor": "Yatırım"},
            "UNLU": {"ad": "Ünlü Yatırım Hol.", "sektor": "Yatırım"},
            "GLRYH": {"ad": "Güler Yatırım Hol.", "sektor": "Yatırım"},
            "DENGE": {"ad": "Denge Yatırım", "sektor": "Yatırım"},
            "HUBVC": {"ad": "Hub Girişim", "sektor": "Yatırım"},
            "YESIL": {"ad": "Yeşil Yatırım", "sektor": "Yatırım"},
            "AVHOL": {"ad": "Avrupa Yatırım Hol.", "sektor": "Yatırım"},
        }

        semboller = [k + ".IS" for k in hisse_rehberi.keys()]
        df = yf.download(semboller, period="1d", interval="30m", progress=False, threads=5,timeout=20,prepost=False)
        if df.empty:
            return "Veri Alınamadı"


        fiyatlar = df['Close']
        hacim = df['Volume']
        hisse_listesi = []
        for sembol in fiyatlar.columns:
            temiz_kod = sembol.replace('.IS','')
            uzun_isim = hisse_rehberi.get(temiz_kod, {}).get('ad', temiz_kod)
            fiyat_seri = fiyatlar[sembol].dropna()
            hacim_seri = hacim[sembol].dropna()
            ilk_fiyat = fiyat_seri.iloc[0]
            son_fiyat = fiyat_seri.iloc[-1]
            hacim_toplam = float(hacim_seri.sum())
            değişim = ((son_fiyat - ilk_fiyat) / ilk_fiyat) * 100
            hisse_listesi.append({'name' : uzun_isim , 'fiyat' : float(round(son_fiyat,2)) , 'degisim' : float(round(değişim,2)), 'acılıs' : float(round(ilk_fiyat,2)),'Hacim' : hacim_toplam,'sektor': hisse_rehberi.get(temiz_kod, {}).get('sektor', 'Diger')})

        hisse_listesi.sort(key=lambda x: x['fiyat'],reverse=True)
        return render_template("/borsa_menu.html",veriler=hisse_listesi)
    except KeyError as e:
        return f"<h1>📊 Veri Formatı Hatası</h1><p>Borsadan gelen verilerde beklenen veri alanı bulunamadı.</p>"
    except requests.exceptions.Timeout:
        return "<h1>⌛ Sunucu Yanıt Vermiyor</h1><p>Veri kaynağı (Yahoo Finance/Borsa) çok geç yanıt veriyor, lütfen tekrar deneyin.</p>"


    except (requests.exceptions.ConnectionError, ConnectionError):
        return "<h1>🌐 Bağlantı Hatası</h1><p>İnternet bağlantınızı kontrol edin veya veri sağlayıcısının erişilebilir olduğundan emin olun.</p>"

    except ZeroDivisionError:
        return "<h1>🧮 Matematiksel Hata</h1><p>Veri setindeki eksiklikler nedeniyle finansal rasyolar hesaplanamadı (Sıfıra bölme hatası).</p>"

    except pd.errors.EmptyDataError:
        return "<h1>📉 Veri Boş</h1><p>Arattığınız hisse/kripto için geçmiş fiyat verisi bulunamadı.</p>"

    except ccxt.ExchangeError:
        return "<h1>🏛️ Borsa API Hatası</h1><p>Kripto borsasından veri çekilirken borsa kaynaklı bir hata oluştu.</p>"

    except ccxt.AuthenticationError:
        return "<h1>🔑 Yetkilendirme Hatası</h1><p>Borsa API anahtarlarınız hatalı veya süresi dolmuş.</p>"

    except PermissionError:
        return "<h1>🔒 Erişim Yetkisi Yok</h1><p>Sistem dosyalarına veya veritabanına erişim izniniz bulunmuyor.</p>"

    except Exception as e:
        return f"<h1>🛠️ Beklenmedik Bir Hata</h1><p>Sistem yöneticisine iletilmek üzere kaydedildi./p>"
    finally:
        if df is not None:
            del df
        if fiyatlar is not None:
            del fiyatlar
        if hacim is not None:
            del hacim
        if hisse_listesi is not None:
            del hisse_listesi
        gc.collect()
        gc.collect(generation=2)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
