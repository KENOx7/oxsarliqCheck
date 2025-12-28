import streamlit as st
import pandas as pd
import PyPDF2
import re
import io
from difflib import SequenceMatcher

# --- KONFİQURASİYA ---
st.set_page_config(page_title="Professional Sual Müqayisə", layout="wide")

# --- KÖMƏKÇİ FUNKSİYALAR ---

def normalize_aggressive(text):
    """
    Müqayisə üçün çox aqressiv təmizləmə:
    1. Bütün boşluqları silir (daxilind ə -> daxilində olması üçün).
    2. Nömrələri və simvolları ləğv edir.
    """
    if not isinstance(text, str):
        return ""
    
    # 1. Kiçik hərf
    text = text.lower()
    
    # 2. Əvvəldəki nömrələri silmək (Məs: "286 .", "1.", "5)")
    text = re.sub(r'^\d+[\.\)\s]*', '', text)
    
    # 3. Simvolları silmək (nöqtə, vergül, sual, mötərizə və s.)
    text = re.sub(r'[^\w]', '', text)
    
    return text

def normalize_readable(text):
    """Ekranda göstərmək üçün yüngül təmizləmə"""
    if not isinstance(text, str): return ""
    return re.sub(r'^\d+[\.\)\s]*', '', text).strip()

def similar(a, b):
    """İki mətn arasındakı oxşarlıq faizi"""
    return SequenceMatcher(None, a, b).ratio()

def extract_pdf_lines(pdf_file):
    lines = []
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        full_text = ""
        for page in reader.pages:
            full_text += page.extract_text() + "\n"
        
        raw_lines = full_text.split('\n')
        for line in raw_lines:
            line = line.strip()
            if len(line) > 5: 
                lines.append(line)
    except Exception as e:
        st.error(f"PDF oxuma xətası: {e}")
    return lines

# --- ƏSAS HİSSƏ ---

st.title("🚀 Super-Smart Sual Müqayisə (Fix)")
st.markdown("Bu versiya PDF-dəki **aralı düşən hərfləri (m ə s ə l ə n)** birləşdirərək yoxlayır.")

col1, col2 = st.columns(2)
with col1:
    uploaded_excel = st.file_uploader("1. Excel/CSV Faylı", type=['xlsx', 'csv'])
with col2:
    uploaded_pdf = st.file_uploader("2. PDF Faylı", type=['pdf'])

if uploaded_excel and uploaded_pdf:
    if st.button("🔍 Dəqiq Analiz Et", type="primary"):
        with st.spinner('Hərflər birləşdirilir və yoxlanılır...'):
            
            # 1. Excel Oxu
            try:
                if uploaded_excel.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_excel)
                else:
                    df = pd.read_excel(uploaded_excel)
                
                # Sual sütununu tap
                target_col = None
                for col in df.columns:
                    if "sual" in col.lower() or "question" in col.lower():
                        target_col = col
                        break
                if not target_col:
                    target_col = df.columns[1] 
                
                excel_questions = df[target_col].dropna().astype(str).tolist()
                
            except Exception as e:
                st.error("Excel xətası.")
                st.stop()

            # 2. PDF Oxu
            pdf_lines = extract_pdf_lines(uploaded_pdf)

            # 3. Analiz Hazırlığı (Aqressiv Təmizləmə)
            pdf_data = []
            for original in pdf_lines:
                # 'clean' sahəsi müqayisə üçün (boşluqsuz), 'display' oxumaq üçün
                pdf_data.append({
                    "original": original, 
                    "clean": normalize_aggressive(original),
                    "display": normalize_readable(original)
                })

            results = []

            # 4. Müqayisə Dövrü
            for ex_q in excel_questions:
                ex_clean = normalize_aggressive(ex_q) # Boşluqsuz versiya
                if len(ex_clean) < 3: continue

                best_match_original = "---"
                best_score = 0.0

                # PDF içində axtar
                for pdf_item in pdf_data:
                    # Aqressiv (boşluqsuz) versiyaları müqayisə edirik
                    score = similar(ex_clean, pdf_item["clean"])
                    
                    if score > best_score:
                        best_score = score
                        best_match_original = pdf_item["original"]
                
                # Statusu təyin et
                status = "Tapılmadı"
                # İndi 100% (1.0) olma ehtimalı çox yüksəkdir, çünki boşluqları sildik
                if best_score > 0.96: 
                    status = "Tam Eyni"
                elif best_score >= 0.70:
                    status = "Oxşar / Səhv ola bilər"
                
                results.append({
                    "Excel-dəki Sual": ex_q,
                    "PDF-də Tapılan": best_match_original,
                    "Oxşarlıq": round(best_score * 100, 1),
                    "Status": status
                })

            results_df = pd.DataFrame(results)

            # 5. Ekrana Çıxarmaq
            match_count = len(results_df[results_df["Status"] == "Tam Eyni"])
            similar_count = len(results_df[results_df["Status"] == "Oxşar / Səhv ola bilər"])
            missing_count = len(results_df[results_df["Status"] == "Tapılmadı"])

            st.success(f"Analiz Bitdi! Nəticə:")
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            col_stat1.metric("✅ Tam Eyni", match_count)
            col_stat2.metric("⚠️ Oxşar", similar_count)
            col_stat3.metric("❌ Tapılmadı", missing_count)

            tab1, tab2, tab3 = st.tabs(["Nəticələr (Cədvəl)", "Yalnız Fərqlilər", "Yüklə"])

            with tab1:
                st.dataframe(results_df, use_container_width=True)

            with tab2:
                # Exceldə olub PDF-də olmayanlar
                st.write("Aşağıdakılar Excel-də var amma PDF-də tapılmadı (və ya çox fərqlidir):")
                st.dataframe(results_df[results_df["Status"] == "Tapılmadı"], use_container_width=True)

            with tab3:
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    results_df.to_excel(writer, index=False)
                
                st.download_button(
                    label="📥 Nəticəni Excel kimi yüklə",
                    data=buffer.getvalue(),
                    file_name="Deqiq_Muqayise_Neticesi.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )