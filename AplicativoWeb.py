import streamlit as st
import pandas as pd
import urllib.request
import urllib.parse
import urllib.error
import json
import time
import io

# Configuración de la ventana web
st.set_page_config(
    page_title="Motor de Validación SIRE - SUNAT",
    page_icon="📊",
    layout="centered"
)

st.title("📊 Motor de Validación SIRE - SUNAT")
st.write("Herramienta de validación masiva de comprobantes con la API de SUNAT.")

# ============================================================
# 1. DATOS DE ENTRADA (Formulario web)
# ============================================================
st.header("1. Credenciales SUNAT")

col1, col2 = st.columns(2)
with col1:
    RUC_EMPRESA = st.text_input("RUC Empresa:", max_chars=11).strip()
    CLIENT_ID = st.text_input("Client ID:").strip()

with col2:
    CLIENT_SECRET = st.text_input("Client Secret:", type="password").strip()

# ============================================================
# 2. CARGAR ARCHIVO TXT
# ============================================================
st.header("2. Propuesta SIRE (Archivo TXT)")
archivo_txt = st.file_uploader("Seleccione el archivo TXT de la propuesta SIRE", type=["txt"])


# ============================================================
# FUNCIONES DE CONSULTA A SUNAT (Conservan tu lógica exacta)
# ============================================================

def obtener_token(client_id, client_secret):
    url_token = (
        "https://api-seguridad.sunat.gob.pe/v1/"
        "clientesextranet/"
        + client_id +
        "/oauth2/token/"
    )

    datos = {
        "grant_type": "client_credentials",
        "scope": "https://api.sunat.gob.pe/v1/contribuyente/contribuyentes",
        "client_id": client_id,
        "client_secret": client_secret
    }

    datos_codificados = urllib.parse.urlencode(datos).encode("utf-8")

    solicitud = urllib.request.Request(
        url_token,
        data=datos_codificados,
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(solicitud, timeout=30) as respuesta:
            contenido = respuesta.read().decode("utf-8")
            resultado = json.loads(contenido)
            return resultado.get("access_token")
    except urllib.error.HTTPError as error:
        st.error(f"🔴 Error HTTP en autenticación SUNAT: {error.code}")
        try:
            mensaje = error.read().decode("utf-8", errors="replace")
            st.error(f"Detalle: {mensaje}")
        except:
            pass
        return None
    except Exception as error:
        st.error(f"🔴 Error de conexión con SUNAT: {error}")
        return None


def consultar_comprobante(token, ruc_empresa, ruc_emisor, tipo_comprobante, serie, numero, fecha, monto):
    url_consulta = (
        "https://api.sunat.gob.pe/v1/"
        "contribuyente/contribuyentes/"
        + ruc_empresa +
        "/validarcomprobante"
    )

    datos = {
        "numRuc": str(ruc_emisor).strip(),
        "codComp": str(tipo_comprobante).strip(),
        "numeroSerie": str(serie).strip(),
        "numero": int(numero),
        "fechaEmision": str(fecha).strip(),
        "monto": float(monto)
    }

    datos_json = json.dumps(datos).encode("utf-8")

    solicitud = urllib.request.Request(
        url_consulta,
        data=datos_json,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        },
        method="POST"
    )

    with urllib.request.urlopen(solicitud, timeout=30) as respuesta:
        contenido = respuesta.read().decode("utf-8")
        return json.loads(contenido)


# ============================================================
# 3. EJECUCIÓN CON BOTÓN
# ============================================================
st.header("3. Procesar Validación")

if st.button("🚀 Iniciar Validación de Comprobantes", type="primary"):
    # Validaciones básicas de campos vacíos
    if not RUC_EMPRESA or not CLIENT_ID or not CLIENT_SECRET:
        st.warning("⚠️ Debe ingresar RUC, Client ID y Client Secret.")
    elif archivo_txt is None:
        st.warning("⚠️ Debe seleccionar un archivo TXT.")
    else:
        st.info("🔄 Solicitando token a SUNAT...")
        token = obtener_token(CLIENT_ID, CLIENT_SECRET)

        if token is None:
            st.error("⛔ El proceso se detuvo porque SUNAT no entregó el token.")
        else:
            st.success("✅ Token obtenido correctamente.")

            # Lectura del archivo TXT subido
            try:
                df = pd.read_csv(
                    archivo_txt,
                    sep="|",
                    encoding="utf-8",
                    dtype=str,
                    on_bad_lines="skip"
                )
                df.columns = df.columns.str.strip()
                st.write(f"📄 Comprobantes encontrados en el archivo: **{len(df)}**")
            except Exception as error:
                st.error(f"🔴 Error al leer el archivo TXT: {error}")
                st.stop()

            # Nombres de columnas esperados
            COL_FECHA = "Fecha de emisión"
            COL_SERIE = "Serie del CDP"
            COL_NUMERO = "Nro CP o Doc. Nro Inicial (Rango)"
            COL_RUC = "Nro Doc Identidad"
            COL_MONTO = "Total CP"

            estados = []
            estados_ruc = []
            condiciones = []
            observaciones = []

            # Componentes visuales de progreso
            barra_progreso = st.progress(0)
            texto_estado = st.empty()
            total_filas = len(df)

            st.write("🛰️ Consultando comprobantes en SUNAT...")

            for indice, fila in df.iterrows():
                try:
                    fecha_original = str(fila[COL_FECHA]).strip()
                    fecha_convertida = pd.to_datetime(fecha_original, dayfirst=True, errors="coerce")
                    
                    if pd.isna(fecha_convertida):
                        raise ValueError("Fecha inválida: " + fecha_original)

                    fecha = fecha_convertida.strftime("%d/%m/%Y")
                    serie = str(fila[COL_SERIE]).strip().upper()

                    if serie.startswith("F"):
                        tipo = "01"
                    elif serie.startswith("B"):
                        tipo = "03"
                    elif serie.startswith("E"):
                        tipo = "01"
                    else:
                        tipo = "01"

                    numero = str(fila[COL_NUMERO]).strip().split(".")[0]
                    monto = str(fila[COL_MONTO]).replace(",", "").strip()

                    resultado = consultar_comprobante(
                        token=token,
                        ruc_empresa=RUC_EMPRESA,
                        ruc_emisor=fila[COL_RUC],
                        tipo_comprobante=tipo,
                        serie=serie,
                        numero=numero,
                        fecha=fecha,
                        monto=monto
                    )

                    data = resultado.get("data", {})
                    estado = data.get("estadoCp", "")
                    estado_ruc = data.get("estadoRuc", "")
                    condicion = data.get("condDomiRuc", "")
                    observacion = data.get("observaciones", "")

                    if isinstance(observacion, list):
                        observacion = " | ".join(map(str, observacion))

                    estados.append(estado)
                    estados_ruc.append(estado_ruc)
                    condiciones.append(condicion)
                    observaciones.append(observacion)

                except urllib.error.HTTPError as error:
                    estados.append(f"HTTP_{error.code}")
                    estados_ruc.append("")
                    condiciones.append("")
                    try:
                        mensaje = error.read().decode("utf-8", errors="replace")
                    except:
                        mensaje = "Error HTTP"
                    observaciones.append(mensaje)

                except Exception as error:
                    estados.append("ERROR")
                    estados_ruc.append("")
                    condiciones.append("")
                    observaciones.append(str(error))

                # Actualización de la barra de progreso
                progreso_actual = (indice + 1) / total_filas
                barra_progreso.progress(progreso_actual)
                texto_estado.text(f"Procesando {indice + 1} de {total_filas} comprobantes...")

                time.sleep(0.2)

            # Agregar resultados al DataFrame
            df["Estado_SUNAT_CPE"] = estados
            df["Estado_RUC"] = estados_ruc
            df["Condicion_Domicilio"] = condiciones
            df["Observaciones_SUNAT"] = observaciones

            st.success("🎉 ¡Validación terminada exitosamente!")

            # Guardar el archivo Excel en memoria para la descarga
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, index=False)
            output.seek(0)

            # Botón de descarga del Excel generado
            st.download_button(
                label="📥 Descargar Resultado Excel",
                data=output,
                file_name="Resultado_Validacion_SIRE_Final.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )