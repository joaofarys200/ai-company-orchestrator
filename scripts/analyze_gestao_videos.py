import os
import glob
import base64
import requests
import json
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv('.env')
key = os.getenv('GEMINI_API_KEY')

videos = [
    ('doc_vid_2cc2c43e640b', '010 Projects - part I.wmv'),
    ('doc_vid_62bacbb12475', '010 Projects - part II.wmv'),
    ('doc_vid_91c228841b4b', '010 Projects - part III.wmv'),
    ('doc_vid_98aff7821f20', '030 Initiating.wmv'),
    ('doc_vid_37691f97c10b', '000 Planning - part I.wmv'),
    ('doc_vid_3e591d4e4540', '000 Planning - part II.wmv'),
    ('doc_vid_2f962e0f2158', '000 Planning - part III.wmv'),
    ('doc_vid_3835adeef512', '000 Planning - part IV.wmv'),
]

out_data = {}
out_file = 'data/study/resumo_gestao_videos.json'
if os.path.exists(out_file):
    try:
        out_data = json.load(open(out_file, 'r', encoding='utf-8'))
    except Exception:
        out_data = {}

for doc_id, fname in videos:
    if fname in out_data and len(out_data[fname]) > 100:
        print(f'[CACHE] {fname} já analisado.')
        continue
    p = os.path.join('data/study/keyframes', doc_id)
    if not os.path.exists(p):
        print(f'[AVISO] Sem keyframes para {doc_id}')
        continue
    frames = sorted([f for f in os.listdir(p) if f.endswith('.jpg')])
    sample = [frames[0], frames[len(frames)//4], frames[len(frames)//2], frames[3*len(frames)//4], frames[-1]]
    
    parts = [{'text': f'Analisa detalhadamente estes 5 diapositivos da aula "{fname}" de Gestão de Projetos lecionada pelo Prof. João Varajão (Universidade do Minho). Identifica de forma rigorosa:\n1. Tema principal do vídeo;\n2. Processos do standard (PMBOK / ISO 21500) apresentados com respetivos Primary Inputs e Primary Outputs (tabelas);\n3. Conceitos, frameworks, modelos e ferramentas explicadas;\n4. Síntese detalhada do conteúdo da aula.'}]
    for sf in sample:
        fp = os.path.join(p, sf)
        with open(fp, 'rb') as f:
            b64 = base64.b64encode(f.read()).decode('utf-8')
        parts.append({'inline_data': {'mime_type': 'image/jpeg', 'data': b64}})
    
    payload = {'contents': [{'parts': parts}]}
    res = requests.post(f'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={key}', json=payload)
    if res.status_code == 200:
        ans = res.json()['candidates'][0]['content']['parts'][0]['text']
        out_data[fname] = ans
        print(f'[OK] Analisado {fname}')
        with open(out_file, 'w', encoding='utf-8') as f:
            json.dump(out_data, f, ensure_ascii=False, indent=2)
    else:
        print(f'[ERRO] {fname}: {res.status_code}')

print('CONCLUIDO! Total de vídeos no resumo:', len(out_data))
