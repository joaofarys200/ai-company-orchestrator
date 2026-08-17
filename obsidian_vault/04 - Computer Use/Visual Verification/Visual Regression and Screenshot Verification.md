---
type: concept
domain: computer-use
difficulty: intermediate
tags:
  - computer-use
  - playwright
  - visual-regression
  - screenshots
  - validation
status: verified
---

# 📸 Visual Regression and Screenshot Verification

## 1. Definição & Motivação
A **Verificação Visual (Visual Regression Testing)** é o processo de capturar screenshots de interfaces web em alta fidelidade e compará-los contra imagens de referência (*Gold Masters*) ou submetê-los a modelos multimodais de visão para detetar:
- Elementos quebrados ou sobrepostos (*layout shifts*);
- Cores de contraste ilegíveis ou falhas de renderização CSS;
- Modais bloqueantes ou mensagens de erro não captadas pelo DOM puro.

---

## 2. Padrão de Captura de Alta Fidelidade no Playwright

```python
from playwright.async_api import Page
import io
from PIL import Image, ImageChops

async def capture_deterministic_screenshot(page: Page, output_path: str):
    # 1. Forçar animações CSS a parar para garantir determinismo de pixels
    await page.add_style_tag(content="""
        *, *::before, *::after {
            transition: none !important;
            animation: none !important;
            caret-color: transparent !important;
        }
    """)
    # 2. Aguardar carregamento completo de fontes
    await page.evaluate("document.fonts.ready")
    
    # 3. Capturar screenshot
    await page.screenshot(path=output_path, full_page=False)

def calculate_pixel_diff_ratio(img1_path: str, img2_path: str) -> float:
    """Calcula a percentagem de pixels diferentes entre duas imagens."""
    img1 = Image.open(img1_path).convert("RGB")
    img2 = Image.open(img2_path).convert("RGB")
    
    diff = ImageChops.difference(img1, img2)
    stat = diff.getbbox()
    if stat is None:
        return 0.0  # Imagens 100% idênticas
        
    # Contar pixels não pretos na diferença
    diff_pixels = sum(1 for pixel in diff.getdata() if sum(pixel) > 10)
    total_pixels = img1.size[0] * img1.size[1]
    return (diff_pixels / total_pixels) * 100.0
```

---

## 3. Feedback Loop Multimodal para Agentes
Quando a diferença de pixels ultrapassa um limiar (ex: $> 1.0\%$), a imagem de diff é enviada diretamente para o modelo multimodal do agente com a pergunta:
> *"O screenshot capturado apresenta regressão visual ou erro de interface? Descreve o problema observado."*

---

## 4. Related Concepts
- [[Playwright Architecture and Automation Protocol]]
- [[DOM State Inspection and Resilient Locators]]
- [[Unit Tests vs End-to-End Tests in Agent Validation]]

---

## 5. Sources
- *Playwright Visual Comparisons Guide*: https://playwright.dev/python/docs/test-snapshots
- *W3C Web Content Accessibility Guidelines (WCAG) 2.1 - Visual Contrast*: https://www.w3.org/TR/WCAG21/
