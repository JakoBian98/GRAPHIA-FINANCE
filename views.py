import matplotlib
import matplotlib.pyplot as plt
from flask import Flask,render_template , request , make_response
from datetime import datetime
import pandas as pd
import yfinance as yf
from itsdangerous import Signer
import io
import base64
import numpy as np
import os
import re


matplotlib.use('Agg')


app = Flask(__name__)



@app.route("/")
def selamün_aleyküm():
    return render_template("hello.html")



@app.route("/Finans")
def finans():
    return render_template("finans_menu.html")

@app.route("/Finance",methods=['POST'])
def Finance():
    try:
        sembol = request.form.get("hisse").upper().strip()
        veri = yf.Ticker(sembol)
        gecmis = veri.history(period="1d")
        if not sembol:
            return "Hisse Kısmı Boş Olamaz"

        try:
            df = yf.download(sembol, period="5d", interval="1d", progress=False)
        except:
            df = pd.DataFrame()

        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            fiyat = df.iloc[-1]
            tarih = df.index[-1].strftime("%Y.%m.%d")
            kapanıs = float(df['Close'].iloc[-1])
            en_yuksek = df['High'].max()
            en_dusuk = df['Low'].min()
            beta = veri.info.get('Beta')
            market_cap = veri.info.get('marketCap')
            temettü = veri.info.get('dividendYield')
            temettü_verimi = veri.info.get('trailingAnnualDividendYield')
            toplam_hisse_sayısı = veri.info.get("sharesOutstanding")
            max_geçmiş = veri.history(period="max",auto_adjust=False,actions=False)
            öz_kaynak_karlılığı = veri.info.get("returnOnEquity")
            defter_değeri = veri.info.get('priceToBook')
            borç_bölü_özkaynak_oran = veri.info.get('debtToEquity')
            short_ratio = veri.info.get('shortRatio',np.nan)
            kurumsal_yatırımcılar_sahiplik_oranı = veri.info.get('heldPercentInstitutions')
            adres = veri.info.get('address1')
            çalışan_sayısı = veri.info.get("fullTimeEmployees")
            ceo = veri.info.get('companyOfficers',np.nan)[0]['name']
            gelir = veri.info.get('totalRevenue',np.nan)
            gelir_bölü_çalışan = gelir / çalışan_sayısı
            halka_arz_ms = veri.info.get('firstTradeDateMilliseconds')
            geçmiş_hepsi = veri.history(period="max",interval="1d")
            özet = veri.info.get("longBusinnesSummary")
            öneriler = veri.recommendations
            long_name = veri.info.get('longName')
            bilanço_tarihi = "Belirtilmemiş"
            bilanço_beklenti = "Veri Yok"
            kar = veri.earnings_dates
            veri_ath = yf.download(sembol, period="max", interval="1d", progress=False)
            veri_ath = pd.DataFrame(veri_ath)
            if isinstance(veri_ath.columns, pd.MultiIndex):
                veri_ath.colunms = veri_ath.columns.get_level_values(0)
            ATH = float(veri_ath['Close'].max())
            if kar is not None or not  kar.empty:
                future_earnings = kar[kar.index > pd.Timestamp.now(tz='UTC')]
                if not future_earnings.empty:
                   en_yakın_bilanço = future_earnings.iloc[0]
                   bilanço_tarihi = en_yakın_bilanço.strftime("%Y,%m-%d")
                   bilanço_beklenti = future_earnings.iloc[0].get('EPS Estimate')
                   if pd.notnull(bilanço_beklenti):
                       bilanço_beklenti = bilanço_beklenti

            ema_df = veri.history(period="1y")
            if not ema_df.empty:
                if isinstance(ema_df.columns,pd.MultiIndex):
                    ema_df.columns = ema_df.columns.get_level_values(0)

            ema_listesi_sözlük = {}
            ema_listesi_tablo = []
            periyotlar = range(20,220,20)
            son_fiyat = ema_df['Close'].iloc[-1]
            alış_sinyali = 0
            satış_sinyali = 0
            for p in periyotlar:
                sütun_adı = f"EMA-{p}"
                ema_değeri = ema_df['Close'].ewm(span=p,adjust=False).mean()
                güncel_ema = float(ema_değeri.iloc[-1])
                ema_listesi_sözlük[sütun_adı] = round(güncel_ema,2)

                if son_fiyat > güncel_ema:
                    alış_sinyali += 1
                elif son_fiyat == güncel_ema:
                    alış_sinyali += 0
                    satış_sinyali += 0
                else:
                    satış_sinyali += 1

                if alış_sinyali > 7:
                    gösterge = "Güçlü Al"
                    ema_renk = "Succes"
                elif alış_sinyali > 5:
                    gösterge = "Al"
                    ema_renk = "Succes"
                elif satış_sinyali >7:
                    gösterge = "Güçlü Sat"
                    ema_renk = "danger"
                elif satış_sinyali >5:
                    gösterge = "Sat"
                    ema_renk = "danger"
                else:
                    gösterge = "NÖTR/BEKLE"
                    ema_renk = "warning"

                ema_listesi_tablo.append({
                    'periyot': f"EMA-{p}",
                    'deger': güncel_ema,
                    'sinyal': gösterge,
                    'renk': ema_renk
                })


            if öneriler is not None and not öneriler.empty:
                son_öneriler = öneriler.tail(5)
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
            if likitide_oranı:
                if likitide_oranı >= 1:
                    likitide_durumu = f"{likitide_oranı} Likitide Çok Güçlü Borçları Anında kapıyabilir"
                elif likitide_oranı > 0.80:
                    likitide_durumu =f"{likitide_oranı} Likitide Dengeli . Nakit Akışın Devamı gerekli"
                elif likitide_oranı > 0.50:
                    likitide_durumu = f"{likitide_oranı} Likitide Zayıf Dikkatli Olunması Gerekli"
                else:
                    likitide_durumu = f"{likitide_oranı} Likitide Krizi : Şirketin Nakit Durumu Çok Tehlikeli"
            else:
                likite_durumu = f"Veri Alınamadı"
            peg_ratio = veri.info.get('trailingPegRatio')



            if peg_ratio:
                if peg_ratio <1:
                    peg_durum = f"{peg_ratio} Hisse Çok Ucuz (Kelepir)"
                elif peg_ratio <2:
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
            ma200 =  veri.info.get('twoHundredDayAverage')
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
            if short_ratio >3:
                durum = f"Dikkat Açığa Satış Baskısı Var"
            elif short_ratio <3:
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
            if hedef_fiyat:
                potansiyel = ((hedef_fiyat - kapanıs) / kapanıs) * 100
            if not tavsiye or not hedef_fiyat:
                hedef_fiyat = np.nan
                tavsiye = np.nan

            skor = 0
            maks_skor = 100

            if cari_oran and cari_oran >= 1.5:
                skor += 20
            elif cari_oran and cari_oran >= 1:
                skor += 10

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

            if skor >=80:
                güven_mesajı = f"🚀Çok Güçlü : Finansal Ve Teknik Göstergeler Mükemmel"
                renk = "succes" #HTML DE YEŞİL
            elif skor>= 50:
                güven_mesajı = f"⚖️Dengeli : Şirket Sağlam Ama Bazı Riskler Barındırıyor"
                renk = "warning" #HTML DE SARI
            else:
                güven_mesajı = f"⚠️Riskli : Göstergeler Zayıf Dikkatli Olunmalı"
                renk = "danger" #HTML DE KIRMIZI

            insider_verisi = veri.get_insider_transactions()
            alımlar = insider_mesajı = "İçeriden Alım Bilgisi Yok"
            insider_renk = "text-dim"
            if insider_verisi is not None and not insider_verisi.empty:
                alımlar = insider_verisi[insider_verisi['Transaction'] == "Buy"]
                toplam_alınan_lot = alımlar['Shares'].sum() if not alımlar.empty else 0
                if toplam_alınan_lot > 0:
                    insider_mesajı = (f"Olumlu : Yöneticiler Bu Şirkete Güveniyor")
                    insider_renk = "succes"
                    skor += 15
                else:
                    insider_mesajı = "Son Dönemde Yönetici Seviyesinde Alım Saptanmadı"

            zirveden_uzaklık = ((kapanıs - ATH) / ATH) * 100

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
            if "=X" in sembol or "TRY" in sembol or "USD" in sembol:
                hacim = np.nan
                ortalama_hacim = np.nan
                toplam_hisse_sayısı = np.nan
                gelir_tablosu = np.nan
                hbk = np.nan
                fk_oran = np.nan
                market_cap = np.nan
                temettü = np.nan
                öz_kaynak_karlılığı = np.nan
                hedef_fiyat = np.nan
                tavsiye = np.nan
                potansiyel = np.nan
                kuruluş_yılı = np.nan
                ma_sinyal = np.nan
                iştah = np.nan
                peg_durum = np.nan
                likite_durumu = np.nan
                güven_mesajı = np.nan
                renk = np.nan
                ceo = np.nan
                özet = np.nan

            else:
                hacim = fiyat["Volume"]
                ortalama_hacim = df["Volume"].mean()

            if df.empty:
                return "Hisse Girilmedi"

            return render_template("finanssonuc.html",
                                   hisse=sembol,
                                   fiyat=fiyat,
                                   tarih=tarih,
                                   kapanıs=kapanıs,
                                   en_yuksek=en_yuksek,
                                   en_dusuk=en_dusuk,
                                   hacim=hacim, ortalama_hacim=ortalama_hacim,fk=fk_oran,beta=beta,
                                   market_cap=market_cap,temettü=temettü,temettü_verim=temettü_verimi,
                                   ath=ATH,zirveden_uzaklık=zirveden_uzaklık,
                                   oz_kaynak_karlılığı = öz_kaynak_karlılığı,
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


    except ValueError:
        return "<h1>Seçtiğiniz Kriterlere Uygun Veri Bulunamadı </h1>"
    except KeyError:
        return "<h1>Veri Formatı Eksik Veya Hatalı</h1>"
    except ConnectionError:
        return "<h1>Bağlantı Hatası : Lütfen İnternetinizi Kontrol Edin</h1>"
    except ZeroDivisionError:
        return "<h1>Sistemde Matematiksel Hata Saptandı</h1>"
    except Exception:
        return f"<h1>Sistemsel Bir Hata oluştu"



@app.route("/Hacim_Ekranı")
def hacim_ekranı():
    return render_template("hacimmenu.html")


@app.route("/Hacim",methods=['POST'])
def hacim_bilgisi():
    try:
        period = request.form.get("period")
        interval = request.form.get("interval")
        sembol = request.form.get("hisse").strip().upper()
        GEÇERLİ_PERIOD = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]
        GEÇERLİ_INTERVAL = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "1wk", "1mo"]
        if not sembol:
            return "Hisse Senedi Giriniz"
        if not period or not interval:
            period = "6mo"
            interval = "1d"

        try:
            df = yf.download(sembol, period=period, interval=interval)
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
            if son_hacim > ortalama_hacim + hacim_std:
                renk = "red"
            elif son_hacim < ortalama_hacim - hacim_std:
                renk = "red"
            else:
                renk = "green"

            fig , ax = plt.subplots(figsize=(12,6),dpi=150)
            ax.plot(tarih,hacim,alpha=0.2,color=renk,linewidth=2)
            ax.fill_between(tarih,hacim,alpha=0.4,color=renk,interpolate=True)
            ax.set_xlabel("Zaman")
            ax.set_ylabel("Hacim")
            ax.set_title(f"{sembol} Hacim Değişimi : (%){hacim_fark_yüzde} (Hacim-Zaman Grafiği)")
            ax.grid(True,alpha=0.090)
            plt.tight_layout()
            img = io.BytesIO()
            plt.savefig(img, format='png', bbox_inches='tight', dpi=150)
            img.seek(0)
            hacim_grafik_url = base64.b64encode(img.getvalue()).decode('utf8')
            plt.close()

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
                       son_tarih=df.index[-1].strftime("%Y-%m-%d"),hacim_grafik_url=hacim_grafik_url,hacim_fark_yüzde=round(hacim_fark_yüzde),ilk_hacim=ilk_hacim,
                       trend_renk=trend_renk,trend_ikon=trend_ikon,trend_mesaj=trend_mesaj,fiyat_değişim=fiyat_değişim)

    except ValueError:
        return "<h1>Seçtiğiniz Kriterlere Uygun Veri Bulunamadı </h1>"
    except KeyError:
        return "<h1>Veri Formatı Eksik Veya Hatalı</h1>"
    except ConnectionError:
        return "<h1>Bağlantı Hatası : Lütfen İnternetinizi Kontrol Edin</h1>"
    except ZeroDivisionError:
        return "<h1>Sistemde Matematiksel Hata Saptandı</h1>"
    except Exception:
        return "<h1>Sistemsel Bir Hata oluştu"

@app.route("/Grafikler")
def grafikler():
    return render_template("grafik.html")

@app.route("/Grafik Penceresi",methods=["POST"])
def grafik_penceresi():
    try:
        sembol = request.form.get("hisse")
        interval = request.form.get("interval")
        period = request.form.get("period")
        GEÇERLİ_PERIOD = ["1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"]
        GEÇERLİ_INTERVAL = ["1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "1wk", "1mo"]
        if not sembol:
            return "Hisse Senedi Girniz"
        if not period or not interval:
            period = "6mo"
            interval = "1d"
        doviz_liste = ["USD", "TRY", "GBP", "CHF", "JPY", "SAR"]
        if any(birim in sembol for birim in doviz_liste) and "=X" not in sembol:
            sembol += "=X"

        df = yf.download(sembol, period=period, interval=interval, progress=False)
        if df.empty:
            return "Hisse Senedi Bulunamadı"
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        fiyat = df["Close"]
        degisim = fiyat.iloc[-1] - fiyat.iloc[0]
        degisim_yuzde = (degisim / fiyat.iloc[0]) * 100
        fiyat_renk = "green" if degisim >= 0 else "red"
        ticker = yf.Ticker(sembol)
        info = ticker.info
        long_name = info.get('LongName', sembol)
        veri_ath = yf.download(sembol,period="max",interval="1d",progress=False)
        veri_ath = pd.DataFrame(veri_ath)
        if isinstance(veri_ath.columns,pd.MultiIndex):
            veri_ath.columns = veri_ath.columns.get_level_values(0)
        ath = float(veri_ath['Close'].max())
        atl = float(veri_ath['Close'].min())

        plt.switch_backend('Agg')
        fig, ax1 = plt.subplots(figsize=(10, 6))
        ax1.plot(df.index, fiyat, color=fiyat_renk, linewidth=2)
        ax1.fill_between(df.index, fiyat, fiyat.min(), color=fiyat_renk, alpha=0.1)
        ax1.set_title(f"{sembol} ({long_name}) | Değisim : {degisim:.2f} (%{degisim_yuzde}) ")
        ax1.grid(True, alpha=0.2)
        plt.tight_layout()

        img = io.BytesIO()
        fig.savefig(img, format='png', bbox_inches='tight')
        img.seek(0)
        grafik_url = base64.b64encode(img.getvalue()).decode('utf8')
        plt.close(fig)

        return render_template("analizpaneli.html", hisse=sembol, fiyat_degisim=round(degisim_yuzde, 2),
                               fiyat_renk=fiyat_renk,
                               grafik=grafik_url,ath=ath,atl=atl)

    except ValueError:
        return "<h1>Seçtiğiniz Kriterlere Uygun Veri Bulunamadı </h1>"
    except KeyError:
        return "<h1>Veri Formatı Eksik Veya Hatalı</h1>"
    except ConnectionError:
        return "<h1>Bağlantı Hatası : Lütfen İnternetinizi Kontrol Edin</h1>"
    except ZeroDivisionError:
        return "<h1>Sistemde Matematiksel Hata Saptandı</h1>"
    except Exception:
        return "<h1>Sistemsel Bir Hata oluştu"

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

        df1 = yf.download(sembol1,period=period,interval=interval,progress=False)
        df2 = yf.download(sembol2,period=period,interval=interval,progress=False)

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

        df1_değişim = df1.iloc[-1] - df1.iloc[0]
        df2_değişim = df2.iloc[-1] - df2.iloc[0]
        df1_yüzde = (df1_değişim / fiyat1.iloc[0]) * 100
        df2_yüzde = (df2_değişim / fiyat2.iloc[0]) * 100
        df1_baslangic_fiyat = float(df1["Close"].iloc[0])
        df1_son_fiyat = float(df1["Close"].iloc[-1])
        df2_baslangic_fiyat = float(df2["Close"].iloc[0])
        df2_son_fiyat = float(df2["Close"].iloc[-1])
        df1_yüzde_serisi = (fiyat1 / fiyat1.iloc[0] - 1) * 100
        df2_yüzde_serisi = (fiyat2 / fiyat2.iloc[0] - 1) * 100


        plt.switch_backend('Agg')
        plt.clf()
        fig, ax = plt.subplots(figsize=(12, 6))

        ax.plot(df1.index,df1_yüzde_serisi,label=f"{sembol1} (%)",linewidth=2.5,color="#3182ce")
        ax.plot(df2.index,df2_yüzde_serisi,label=f"{sembol2} (%)",linewidth=2.5,color="#e53e3e")
        ax.set_title(f"{sembol1} Değişim : {df1_değişim} (%{df1_yüzde}) {sembol2} Değişim : {df2_değişim} (%{df2_yüzde})")

        ax.set_ylabel("Bağıl Getiri (%)")
        ax.legend()
        ax.grid(True, linestyle='--', alpha=0.5)


        img = io.BytesIO()
        fig.savefig(img, format='png', bbox_inches='tight')
        img.seek(0)
        grafik_url = base64.b64encode(img.getvalue()).decode('utf8')
        plt.close(fig)

        return render_template("ikilianalizpaneli.html",
                               grafik=grafik_url,
                               hisse=f"{sembol1} vs {sembol2}",
                               sembol1=sembol1,
                               sembol2=sembol2,
                               df1_yuzde=df2_yüzde.iloc[-1],
                               df2_yuzde=df2_yüzde.iloc[-1],
                               df1_baslangic_fiyat=df1_baslangic_fiyat,
                               df1_son_fiyat=df1_son_fiyat,
                               df2_baslangic_fiyat=df2_baslangic_fiyat,
                               df2_son_fiyat=df2_son_fiyat)
    except ValueError:
        return "<h1>Seçtiğiniz Kriterlere Uygun Veri Bulunamadı </h1>"
    except KeyError:
        return "<h1>Veri Formatı Eksik Veya Hatalı</h1>"
    except ConnectionError:
        return "<h1>Bağlantı Hatası : Lütfen İnternetinizi Kontrol Edin</h1>"
    except ZeroDivisionError:
        return "<h1>Sistemde Matematiksel Hata Saptandı</h1>"
    except Exception as e:
        print(e)
        return "<h1>Sistemsel Bir Hata oluştu"

@app.route("/Dolar_Bazlı_Grafik",methods=['POST','GET'])
def dolar_bazlı_grafik():
    return render_template("dolar_grafik.html")


@app.route("/Dolar_Bazlı_Grafik_Ekranı", methods=['POST'])
def dolar_bazlı_grafik_ekranı():
    try:
        sembol = request.form.get("hisse").upper()
        period = request.form.get("period")
        interval = request.form.get("interval")
        dovız_tipi = request.form.get("kur_tipi")
        sembol_df = yf.download(sembol, period=period, interval=interval, progress=False)
        usd_df = yf.download(dovız_tipi, period=period, interval=interval, progress=False)
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
            kur_df = yf.download("USDTRY=X", period=period, interval=interval, progress=False)
            if isinstance(kur_df.columns, pd.MultiIndex):
                kur_df.columns = kur_df.columns.get_level_values(0)

            ortak_tarihler = sembol_df.index.intersection(usd_df.index).intersection(kur_df.index)
            hisse_usd = sembol_df.loc[ortak_tarihler, "Close"] / kur_df.loc[ortak_tarihler, "Close"]
            dolar_bazlı_seri = (sembol_df.loc[ortak_tarihler, "Close"] / kur_df.loc[ortak_tarihler, "Close"]) / \
                               usd_df.loc[ortak_tarihler, "Close"]
        else:
            kur_df = yf.download(dovız_tipi,period=period,interval=interval,progress=False)
            ortak = sembol_df.index.intersection(usd_df.index)
            dolar_bazlı_seri = sembol_df.loc[ortak, "Close"] / usd_df.loc[ortak, "Close"]

        dolar_bazlı_seri = dolar_bazlı_seri.dropna()
        en_yüksek = dolar_bazlı_seri.max()
        en_düşük = dolar_bazlı_seri.min()


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

        fig, ax = plt.subplots(figsize=(12, 6))
        ax.plot(dolar_bazlı_seri.index, dolar_bazlı_seri.values, alpha=0.5, color=renk, linewidth=2)
        ax.fill_between(dolar_bazlı_seri.index, dolar_bazlı_seri.values, color=renk, alpha=0.3, interpolate=True)
        ax.set_title(f"{sembol} | Değişim : {değişim} (%){toplam_degisim_yuzde} {ilk_uc} Bazlı Grafik")
        ax.axhline(y=en_yüksek,color="green",alpha=0.4,linewidth=0.8,linestyle="--")
        ax.axhline(y=en_düşük,color="green",alpha=0.4,linewidth=0.8,linestyle="--")
        plt.xlabel("Tarih")
        plt.ylabel("Fiyat")
        plt.grid(True, alpha=0.1)
        img = io.BytesIO()
        plt.savefig(img, format='png', bbox_inches='tight')
        img.seek(0)
        grafik_url = base64.b64encode(img.getvalue()).decode('utf8')
        plt.close()
        return render_template("Dolar_Bazlı_Grafik.html",
                               grafik=grafik_url,
                               sembol=sembol,
                               son_fiyat=round(son_fiyat, 2),
                               toplam_degisim_yuzde=round(toplam_degisim_yuzde, 2),
                               değişim=round(değişim, 2), period=period, interval=interval)
    except ValueError:
        return "<h1>Seçtiğiniz Kriterlere Uygun Veri Bulunamadı </h1>"
    except KeyError:
        return "<h1>Veri Formatı Eksik Veya Hatalı</h1>"
    except ConnectionError:
        return "<h1>Bağlantı Hatası : Lütfen İnternetinizi Kontrol Edin</h1>"
    except ZeroDivisionError:
        return "<h1>Sistemde Matematiksel Hata Saptandı</h1>"
    except Exception:
        return "<h1>Sistemsel Bir Hata oluştu"



@app.route("/USD_HACİM")
def usd_hacim():
    return render_template("usd_hacim.html")

@app.route("/USD_HACİM_ANALİZ_BİLGİ",methods=['POST'])
def usd_hacim_analiz():
    try:
        sembol = request.form.get("hisse").upper()
        period = request.form.get("period")
        interval = request.form.get("interval")

        df = yf.download(sembol, period=period, interval=interval, progress=False)
        usd_df = yf.download("USDTRY=X", period=period, interval=interval, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if isinstance(usd_df.columns, pd.MultiIndex):
            usd_df.columns = usd_df.columns.get_level_values(0)

        df = df.loc[:, ~df.columns.duplicated()]
        usd_df = usd_df.loc[:, ~usd_df.columns.duplicated()]

        common_dates = df.index.intersection(usd_df.index)
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

        değişim = son_usd_hacim - ilk_usd_hacim
        if değişim > 0:
            renk = "green"
        elif değişim < 0:
            renk = "red"
        else:
            renk = "gray"

        fig, ax = plt.subplots(figsize=(12, 6), dpi=150)
        ax.plot(tarih, usd_hacim_serisi, linewidth=2, alpha=0.2, color=renk)
        ax.fill_between(tarih, usd_hacim_serisi, color=renk, alpha=0.5)
        ax.set_title(f"{sembol} Dolar Bazlı Hacim-Zaman Grafiği Değişim : (%){usd_hacim_fark_yuzde}")
        ax.grid(True, alpha=0.090)
        plt.legend()
        img = io.BytesIO()
        plt.savefig(img, format='png', bbox_inches='tight', facecolor=fig.get_facecolor())
        img.seek(0)
        usd_hacim_grafik_url = base64.b64encode(img.getvalue()).decode('utf8')
        plt.close()
        return render_template("usd_hacim_sonuc.html",
                               usd_hacim_grafik_url=usd_hacim_grafik_url,
                               sembol=sembol,
                               son_usd_hacim=son_usd_hacim,
                               usd_hacim_fark_yuzde=usd_hacim_fark_yuzde, en_yüksek_hacim=en_yüksek_hacim,
                               en_düşük_hacim=en_düşük_hacim, en_düşük_tarih=en_düşük_tarih,
                               en_yüksek_tarih=en_yüksek_tarih)
    except ValueError:
        return "<h1>Seçtiğiniz Kriterlere Uygun Veri Bulunamadı </h1>"
    except KeyError:
        return "<h1>Veri Formatı Eksik Veya Hatalı</h1>"
    except ConnectionError:
        return "<h1>Bağlantı Hatası : Lütfen İnternetinizi Kontrol Edin</h1>"
    except ZeroDivisionError:
        return "<h1>Sistemde Matematiksel Hata Saptandı</h1>"
    except Exception:
        return "<h1>Sistemsel Bir Hata oluştu"


@app.route("/Coinler_Paneli")
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
        df = yf.download(semboller,period="1d",interval="1m",progress=False,threads=True,timeout=12)
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
    except ValueError:
        return "<h1>Seçtiğiniz Kriterlere Uygun Veri Bulunamadı </h1>"
    except KeyError:
        return "<h1>Veri Formatı Eksik Veya Hatalı</h1>"
    except ConnectionError:
        return "<h1>Bağlantı Hatası : Lütfen İnternetinizi Kontrol Edin</h1>"
    except ZeroDivisionError:
        return "<h1>Sistemde Matematiksel Hata Saptandı</h1>"
    except Exception:
        return "<h1>Sistemsel Bir Hata oluştu"

@app.route("/Borsa_Paneli")
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
        df = yf.download(semboller, period="1d", interval="30m", progress=False, threads=50,timeout=13.5)
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
    except ValueError:
        return "<h1>Seçtiğiniz Kriterlere Uygun Veri Bulunamadı </h1>"
    except KeyError:
        return "<h1>Veri Formatı Eksik Veya Hatalı</h1>"
    except ConnectionError:
        return "<h1>Bağlantı Hatası : Lütfen İnternetinizi Kontrol Edin</h1>"
    except ZeroDivisionError:
        return "<h1>Sistemde Matematiksel Hata Saptandı</h1>"
    except Exception:
        return "<h1>Sistemsel Bir Hata oluştu"



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
