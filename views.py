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
        doviz_liste = ["USD", "EUR", "TRY", "GBP", "CHF", "JPY", "SAR"]
        if any(birim in sembol for birim in doviz_liste) and "=X" not in sembol:
            sembol += "=X"
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
            kapanıs = df['Close'].iloc[-1]
            en_yuksek = df['High'].iloc[-1]
            en_dusuk = df['Low'].iloc[-1]
            if "=X" in sembol or "TRY" in sembol or "USD" in sembol:
                hacim = np.nan
                ortalama_hacim = np.nan
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
                                   hacim=hacim, ortalama_hacim=ortalama_hacim)
    except:
        return f"Bir Hata Oluştu"

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
            son_fiyat = float(df['Close'].iloc[-1])
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
                       en_düşük_hacim=en_düşük_hacim,
                       min_volume_idx=min_volume_idx,
                       z_skor=z_skor,
                       renk=renk,ilk_tarih=df.index[0].strftime("%Y-%m-%d"),
                       son_tarih=df.index[-1].strftime("%Y-%m-%d"),hacim_grafik_url=hacim_grafik_url,hacim_fark_yüzde=round(hacim_fark_yüzde),ilk_hacim=ilk_hacim)
    except:
        return f"Bir Hata Oluştu"

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
        doviz_liste = ["USD", "EUR", "TRY", "GBP", "CHF", "JPY", "SAR"]
        if any(birim in sembol for birim in doviz_liste) and "=X" not in sembol:
            sembol += "=X"

        df = yf.download(sembol, period=period, interval=interval, progress=False)
        if df.empty:
            return "Hisse Senedi Bulunamadı"
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        fiyat = df["Close"]
        degisim = fiyat.iloc[-1] - fiyat.iloc[0]
        degisim_yuzde = (degisim / fiyat.iloc[0]) * 100
        fiyat_renk = "green" if degisim >= 0 else "red"
        ticker = yf.Ticker(sembol)
        info = ticker.info
        long_name = info.get('LongName', sembol)

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
                               grafik=grafik_url)

    except:
        return f"Bir Hata Oluştu "

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
    except:
        return f"Bir Hata Oluştu"

@app.route("/Dolar_Bazlı_Grafik",methods=['POST'])
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
    except:
        return f"Bir Hata Oluştu "

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
    except :
        return f"Bir Hata Oluştu "

if __name__ == "__main__":
    app.run(debug=False,port=5006)
