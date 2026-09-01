# Guía de Estilos — Snoop × Claude

## Sistema de Diseño Híbrido · Snoop Consulting

**Principio rector:** Carácter y estructura de Snoop. Atmósfera de fondos de Claude. Tipografía editorial premium. El rojo fuerte de Snoop es el voltaje de marca. Las superficies cremosas de Claude reemplazan el blanco plano. **Fraunces** (display serif upright en H1, italic en sub-heads) \+ **Geist** (sans geométrica para body y UI) introducen el contraste tipográfico editorial que eleva el sistema al nivel de marcas como Ideogram.

---

## 0\. Filosofía de la Fusión

| Decisión | Fuente | Razón |
| :---- | :---- | :---- |
| Color primario | **Snoop** `#D9261C` | El rojo fuerte es la identidad de marca; el coral de Claude es demasiado suave |
| Fondos y superficies | **Claude** `#faf9f5 → #efe9de` | Warm cream editorial en lugar de blanco plano |
| Superficies oscuras | **Claude** `#181715` | Navy más rico para footer y cards de producto |
| Tipografía display (H1) | **Nuevo** Fraunces upright wght 300 | Contraste serif/sans editorial premium; H1 sin itálica \= máxima legibilidad |
| Tipografía sub-heads (H2–H4) | **Snoop** Fraunces italic | La itálica se conserva en sub-heads y gradient titles, no en el H1 |
| Tipografía body / UI | **Nuevo** Geist Variable | Sans geométrica de Vercel; reemplaza IBM Plex Sans en cuerpo, nav y botones |
| Gradiente de headings | **Snoop** `#212121 → #546E7A` | Patrón de marca registrado |
| Cards y layout | **Snoop** radio asimétrico | Patrón signature inconfundible |
| Animaciones | **Snoop** `.reveal-on` / pulso | Comportamiento ya implementado |
| Espaciado | **Snoop** \+ inspiración Claude para secciones | Más aire entre bandas |

---

## 1\. Tokens de Diseño

### 1.1 Paleta de Colores

#### Primario — Rojo Snoop (sin cambios)

| Token | HEX | Uso |
| :---- | :---- | :---- |
| `--color-primary` | `#D9261C` | Color de acción principal, botones CTA, gradiente |
| `--color-primary-light` | `#FF6347` | Hover en botones, animaciones de pulso |
| `--color-primary-dark` | `#A31810` | Gradiente, sombras, pseudoelementos |
| `--color-primary-darker` | `#820E0A` | Pulso profundo, estados activos |
| `--color-primary-darkest` | `#610906` | Rojo más oscuro, solo decorativo |

**Gradiente de marca primario (sin cambios):**

```css
background-image: linear-gradient(180deg, #D9261C 0%, #A31810 100%);
```

#### Superficies — Cream de Claude (reemplaza el blanco de Snoop)

| Token | HEX | Reemplaza a | Uso |
| :---- | :---- | :---- | :---- |
| `--color-canvas` | `#faf9f5` | `#FFFFFF` | Fondo base de página — la diferencia clave |
| `--color-surface-soft` | `#f5f0e8` | `#F6F6F6` | Bandas muy sutiles, divisores de sección |
| `--color-surface-card` | `#efe9de` | `#ECEFF1` | Cards, formularios, secciones wrapper-light |
| `--color-surface-card-strong` | `#e8e0d2` | `#CFD8DC` | Tabs activos, bandas enfatizadas |
| `--color-surface-dark` | `#181715` | *(nuevo)* | Footer, cards de producto/código — navy Claude |
| `--color-surface-dark-elevated` | `#252320` | *(nuevo)* | Cards elevados dentro de bandas oscuras |
| `--color-surface-dark-soft` | `#1f1e1b` | *(nuevo)* | Fondos de bloques de código dentro de dark cards |

**Nota:** `--color-canvas` (`#faf9f5`) es el cambio más importante. Es warm, deliberadamente no blanco puro. Esta elección separa visualmente a Snoop de cualquier otro sitio corporativo que use blanco plano.

#### Secundario y neutrales — Snoop (sin cambios)

| Token | HEX | Uso |
| :---- | :---- | :---- |
| `--color-secondary` | `#546E7A` | Blue-gray, texto secundario, sombras suaves |
| `--color-secondary-light` | `#CFD8DC` | Bordes decorativos, hairlines sobre cream |
| `--color-secondary-lighter` | `#ECEFF1` | Fondos muy suaves (reemplazado en gran parte por cream) |
| `--color-body` | `#212121` | Texto principal |
| `--color-body-medium` | `#424242` | Texto secundario, headings de footer |
| `--color-body-soft` | `#616161` | Texto de apoyo |
| `--color-gray-light` | `#BDBDBD` | Bordes en superficies cream |
| `--color-black` | `#000000` | Negro puro |

#### Hairlines sobre fondos cream

```css
/* Sobre canvas #faf9f5 */
--color-hairline:       #e6dfd8;  /* borde de 1px — casi invisible, elegante */
--color-hairline-soft:  #ebe6df;  /* divisor dentro de la misma banda */

/* Sobre cards #efe9de */
--color-hairline-card:  #BDBDBD;  /* hereda de Snoop para mayor contraste */
```

#### Texto sobre superficies oscuras — Claude (nuevo)

```css
--color-on-dark:        #faf9f5;  /* texto principal en dark surfaces — eco del canvas */
--color-on-dark-soft:   #a09d96;  /* texto secundario, footer body */
--color-on-primary:     #ffffff;  /* texto sobre botones rojos */
```

#### Semánticos (sin cambios)

| Token | HEX | Uso |
| :---- | :---- | :---- |
| `--color-success` | `#5db872` | Estados positivos |
| `--color-warning` | `#d4a017` | Advertencias |
| `--color-error` | `#c64545` | Errores de validación |

---

### 1.2 Tipografía — Sistema Fraunces \+ Geist (v2)

El sistema adopta el patrón editorial **serif display / sans UI** inspirado en Ideogram.ai: títulos grandes en Fraunces (variable serif), todo el resto en Geist (sans geométrica de Vercel). Es la combinación de mayor contraste tipográfico y carácter premium disponible en Google Fonts sin costo de licencia.

#### Familias

| Rol | Familia | Fallback | Carga |
| :---- | :---- | :---- | :---- |
| Display (H1–H4) | **Fraunces** | Georgia, serif | Google Fonts |
| UI / body / nav / buttons | **Geist** | system-ui, sans-serif | Google Fonts |

**Import requerido:**

```html
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;0,9..144,700;1,9..144,300;1,9..144,400;1,9..144,700&family=Geist:wght@300;400;500;600;700&display=swap" rel="stylesheet">
```

**Por qué Fraunces:** Variable font con eje óptico (`opsz`). A tamaño display (`opsz 144`) sus letterforms son dramáticos y únicos — efecto equivalente a Exposure de Atipo Foundry, sin costo de licencia. A tamaños pequeños (`opsz 36`) se vuelve más discreta, comportamiento ideal para un sistema escalable.

**Por qué Geist:** La sans-serif de Vercel, adoptada masivamente en productos tech modernos (shadcn/ui, v0, Vercel dashboard). Geométrica, muy legible en pantallas, con weights desde 300 hasta 700\.

#### Regla clave: H1 upright, sub-heads italic

El H1 usa Fraunces **sin itálica** — prioridad legibilidad en titulares largos. Los H2–H4 dentro de `.h-title` y `.a-title` mantienen la **itálica de Fraunces**, creando un contraste interno (display upright / sub-heads italic) que es marca registrada de publicaciones premium como The Guardian o Financial Times.

```css
/* H1 — upright, light, opsz máximo */
h1 {
  font-family: 'Fraunces', Georgia, serif;
  font-style: normal;
  font-weight: 300;
  font-variation-settings: 'opsz' 144, 'wght' 300;
}

/* H2–H4 — italic, opsz ajustado al tamaño */
h2 {
  font-family: 'Fraunces', Georgia, serif;
  font-style: italic;
  font-weight: 400;
  font-variation-settings: 'opsz' 72, 'wght' 400;
}
h3 {
  font-family: 'Fraunces', Georgia, serif;
  font-style: italic;
  font-weight: 700;
  font-variation-settings: 'opsz' 36, 'wght' 700;
}
h4 {
  font-family: 'Fraunces', Georgia, serif;
  font-style: italic;
  font-weight: 700;
  font-variation-settings: 'opsz' 18, 'wght' 700;
}

/* Todo lo demás — Geist */
body, nav, button, input, .caption {
  font-family: 'Geist', system-ui, sans-serif;
}
```

**Gradiente de texto en headings — Snoop (sin cambios, ahora en Fraunces italic):**

```css
background: linear-gradient(90deg, #212121, #546E7A);
background-clip: text;
-webkit-background-clip: text;
color: transparent;
-webkit-text-fill-color: transparent;
```

#### Jerarquía tipográfica completa

| Nivel | Familia | Tamaño | Peso | Estilo | `opsz` | Uso |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| `h1` | Fraunces | 2.5rem | 300 | **normal** | 144 | Hero — legibilidad máxima en titulares largos |
| `h2` | Fraunces | 2.5rem | 400 | italic | 72 | Secciones principales |
| `h3` | Fraunces | 2.5rem | 700 | italic | 36 | Sub-secciones; gradient text en `.h-title` / `.a-title` |
| `h4` | Fraunces | 1.25rem | 700 | italic | 18 | Subtítulos, etiquetas de categoría |
| `h5` | Geist | 1rem | 600 | normal | — | Footer, labels de card |
| body | Geist | 1rem | 400 | normal | — | Texto corriente |
| body-sm | Geist | 0.875rem | 400 | normal | — | Texto secundario, notas |
| caption | Geist | 0.75rem | 500 | normal | — | Badges, etiquetas pequeñas |
| button | Geist | 0.875rem | 500 | normal | — | Labels de botón |
| nav-link | Geist | 0.875rem | 500 | normal | — | Items de navegación |

**Responsive H1:**

- `≤768px`: `font-size: 2.125rem`, `font-variation-settings: 'opsz' 72, 'wght' 300`  
- `≤576px`: `font-size: 1.625rem`, `font-variation-settings: 'opsz' 36, 'wght' 300`

El eje `opsz` debe ajustarse junto con el font-size — a tamaños pequeños los letterforms de Fraunces se moderan automáticamente, pero declararlo explícitamente garantiza consistencia cross-browser.

---

### 1.3 Sistema de Espaciado — Snoop \+ sección extendida

| Token | Valor | Uso |
| :---- | :---- | :---- |
| `--spacing-xs` | `0.25rem` | Micro-gaps |
| `--spacing-sm` | `0.5rem` | Gaps internos pequeños |
| `--spacing-md` | `0.75rem` | Padding de elementos UI |
| `--spacing-base` | `1rem` | Base unit |
| `--spacing-lg` | `1.25rem` | Gaps de grilla |
| `--spacing-xl` | `1.5rem` | Padding de cards medianas |
| `--spacing-xxl` | `3rem` | Separación entre bloques |
| `--spacing-section` | `6rem` | Padding entre bandas de sección — inspirado en Claude (96px) |
| `--gutter` | `1.5rem` | Gutter de grilla de 12 columnas |

`--spacing-section` es nuevo respecto a la guía original de Snoop. Suma aire editorial entre bandas sin romper el sistema de espaciado existente.

---

### 1.4 Border Radius — Snoop (sin cambios)

El patrón asimétrico es el sello visual más reconocible de Snoop. No se modifica.

| Token | Valor | Uso principal |
| :---- | :---- | :---- |
| `--radius-sm` | `0.25rem` | Elementos muy pequeños, badges |
| `--radius` | `0.5rem` | Inputs, botones estándar |
| `--radius-lg` | `1rem` | Paneles de búsqueda, modales |
| `--radius-xl` | `1.25rem` | Uso decorativo |
| `--radius-xxl` | `2rem` | Cards, CTA — el más usado |

**Patrón signature asimétrico (sin cambios):**

```css
border-radius: 2rem 2rem 0.5rem 2rem; /* esquina inferior-derecha "cortada" */
/* Inversión (cortar inferior-izquierda): */
border-radius: 2rem 2rem 2rem 0.5rem;
```

---

### 1.5 Transiciones y Animaciones — Snoop (sin cambios)

```css
/* Transición estándar de color/fondo */
transition: color .4s ease, background-color .4s ease, border-color .4s ease;

/* Transición de layout (colapso/expansión) */
transition: max-height .7s ease-in-out, opacity .7s ease-in-out;

/* Reveal on scroll */
.reveal-on {
  opacity: 0;
  transform: translateY(2rem);
  transition: opacity .7s ease-in-out, transform .7s ease-in-out;
}
.reveal-on.visible {
  opacity: 1;
  transform: translateY(0);
}
```

---

## 2\. Breakpoints y Responsive — Snoop (sin cambios)

| Nombre | Min-width | Equivale a |
| :---- | :---- | :---- |
| `xs` | `0` | Mobile base |
| `sm` | `576px` | Mobile landscape |
| `md` | `768px` | Tablet portrait |
| `lg` | `992px` | Tablet landscape |
| `xl` | `1200px` | Desktop |
| `xxl` | `1400px` | Desktop grande |

**Contenedores:**

| Breakpoint | max-width |
| :---- | :---- |
| `sm` | `540px` |
| `md` | `720px` |
| `lg` | `960px` |
| `xl` | `1140px` |
| `xxl` | `1328px` |

---

## 3\. Sistema de Grilla — Snoop (sin cambios)

Flexbox de 12 columnas con gutter de `1.5rem`. Clases `.row`, `.col`, `.col-{bp}-{n}`. Ver guía original de Snoop para HTML de referencia.

---

## 4\. Componentes UI

### 4.0 Logo — Identidad Visual

#### Archivos

| Variante | URL | Uso |
| :---- | :---- | :---- |
| **Color** | `https://snoopconsulting.com/wp-content/uploads/2025/05/logo-snoop-1.svg` | Fondos claros: canvas `#faf9f5`, blanco, surface-card |
| **Monocromático** | `https://snoopconsulting.com/wp-content/uploads/2025/05/logo-snoop-black.svg` | Fondos oscuros y rojos — aplicar `filter: invert(1) brightness(2)` |

#### Regla por superficie

| Superficie | Logo | Tratamiento |
| :---- | :---- | :---- |
| Canvas `#faf9f5` | `logo-snoop-1.svg` | Sin filtro — **recomendado** |
| Blanco `#ffffff` | `logo-snoop-1.svg` | Sin filtro — válido |
| Rojo `#D9261C` | `logo-snoop-black.svg` | `filter: invert(1) brightness(2)` — versión blanca |
| Dark navy `#181715` | `logo-snoop-black.svg` | `filter: invert(1) brightness(2)` — versión blanca |
| Surface-card `#efe9de` | `logo-snoop-1.svg` | Sin filtro |

**Regla crítica:** No usar `logo-snoop-1.svg` (color) sobre fondos rojos — el rojo del logo se pierde contra la banda. No usar `logo-snoop-black.svg` sin filtro en fondos oscuros — desaparece. Si se cuenta con un archivo SVG blanco standalone, es preferible al filtro CSS.

#### Posicionamiento — Top Left

El logo ocupa la esquina superior izquierda del header en todas las páginas. Es el único elemento permitido a la izquierda del nav.

```css
/* ── Logo en header ── */
.header-logo {
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.header-logo img {
  height: 2rem;          /* 32px — tamaño por defecto */
  width: auto;
  display: block;
}

/* Responsive */
@media (max-width: 768px) {
  .header-logo img {
    height: 1.75rem;     /* 28px en tablet */
  }
}
@media (max-width: 576px) {
  .header-logo img {
    height: 1.5rem;      /* 24px en mobile */
  }
}
```

**HTML de referencia:**

```html
<!-- Header — logo top-left con variante automática por superficie -->
<header class="header">
  <div class="container">
    <div class="header-inner">

      <!-- Logo: variante color sobre canvas claro -->
      <a href="/" class="header-logo" aria-label="Snoop Consulting">
        <img
          src="https://snoopconsulting.com/wp-content/uploads/2025/05/logo-snoop-1.svg"
          alt="Snoop Consulting"
          width="120" height="32"
        />
      </a>

      <nav class="nav-menu"><!-- ... --></nav>
    </div>
  </div>
</header>
```

#### Logo en footer (dark navy)

```css
.footer-logo img {
  height: 1.75rem;
  width: auto;
  filter: invert(1) brightness(2); /* negro → blanco sobre #181715 */
  display: block;
  margin-bottom: 1rem;
}
```

```html
<!-- Footer — logo white sobre dark -->
<a href="/" class="footer-logo" aria-label="Snoop Consulting">
  <img
    src="https://snoopconsulting.com/wp-content/uploads/2025/05/logo-snoop-black.svg"
    alt="Snoop Consulting"
    width="120" height="28"
    style="filter: invert(1) brightness(2);"
  />
</a>
```

#### Logo en bandas rojas (featured)

```css
.featured-logo img {
  height: 1.75rem;
  width: auto;
  filter: invert(1) brightness(2); /* negro → blanco sobre #D9261C */
}
```

---

### 4.1 Header

**Estructura:** Snoop (sin cambios)  
**Fondo:** `--color-canvas` (`#faf9f5`) en lugar de blanco  
**Logo:** `logo-snoop-1.svg` — top-left, `height: 2rem` (ver §4.0)

```css
.header {
  background-color: var(--color-canvas); /* #faf9f5 — antes: #FFFFFF */
  /* Estado con scroll */
}
.header.alter {
  background-color: rgba(250, 249, 245, 0.85); /* canvas al 85% + blur */
  backdrop-filter: blur(8px);
}

/* Layout interno: logo izquierda · nav derecha */
.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--header-height); /* 5.5rem */
}
```

**Nav links:** `--color-body` (`#212121`), hover `--color-primary` (`#D9261C`)  
**Item activo:** `--color-primary`

---

### 4.2 Botones

#### Botón primario — Snoop rojo (sin cambios)

```css
.button-primary {
  background-image: linear-gradient(180deg, #D9261C 0%, #A31810 100%);
  color: #ffffff;
  border: none;
  border-radius: var(--radius);       /* 0.5rem */
  padding: 0.375rem 1.5rem;
  font-weight: 500;
  transition: background-color .4s ease, color .4s ease;
}
.button-primary:hover {
  background: #FF4D4D;
}
```

#### Botón secundario — adaptado a cream

```css
.button-secondary {
  background-color: var(--color-canvas);   /* antes: #FFFFFF */
  color: var(--color-body);
  border: 1px solid var(--color-hairline); /* #e6dfd8 sobre cream */
  border-radius: var(--radius);
  padding: 0.375rem 1.5rem;
  font-weight: 500;
}
.button-secondary:hover {
  background-color: var(--color-surface-soft); /* #f5f0e8 */
  border-color: var(--color-gray-light);
}
```

#### Botón secundario sobre dark surface (nuevo)

```css
.button-secondary-on-dark {
  background-color: var(--color-surface-dark-elevated); /* #252320 */
  color: var(--color-on-dark);
  border: 1px solid rgba(255,255,255,0.12);
  border-radius: var(--radius);
  padding: 0.375rem 1.5rem;
  font-weight: 500;
}
```

#### Button-go — Snoop (sin cambios)

```css
.button-go {
  display: flex;
  justify-content: space-between;
  background-image: linear-gradient(180deg, #D9261C, #A31810);
  border-radius: 2rem 2rem 0.5rem 2rem;
  color: #ffffff;
}
.button-go:hover {
  background: #FF4D4D;
  border-radius: 2rem;
}
```

#### CTA animado — Snoop (sin cambios)

`.call-to-action` con animación `pulse`. Sin modificaciones.

---

### 4.3 Cards

#### Card estándar — superficie cream en lugar de rgba blue-gray

```css
/* Antes */
background-color: rgba(236, 239, 241, 0.16); /* blue-gray-lighter al 16% */

/* Ahora */
background-color: var(--color-surface-card); /* #efe9de */
border: 1px solid #ffffff;
border-radius: 2rem 2rem 0.5rem 2rem;
box-shadow: rgba(84, 110, 122, 0.4) 0 0 8px -2px;
```

El patrón asimétrico y la sombra azul-gris se mantienen intactos — solo cambia el relleno de fondo.

#### Card oscura (nuevo — de Claude)

Para secciones de producto, código, o featured tier:

```css
.card-dark {
  background-color: var(--color-surface-dark);          /* #181715 */
  color: var(--color-on-dark);
  border-radius: 2rem 2rem 0.5rem 2rem;
  padding: 2rem;
}
.card-dark-elevated {
  background-color: var(--color-surface-dark-elevated); /* #252320 */
}
```

#### Formulario — cream en lugar de blanco

```css
.form {
  border: 1px solid var(--color-secondary-lighter); /* #ECEFF1 */
  border-radius: var(--radius-xxl);                 /* 2rem */
  padding: 3rem;
  overflow: hidden;
  background-color: var(--color-surface-card);      /* #efe9de — antes: #FFFFFF */
}
```

---

### 4.4 Secciones Featured

#### Featured Slogan y Featured Shortcut — Snoop (sin cambios)

Gradiente rojo de fondo, texto blanco, CTA animado. Sin modificaciones.

#### Wrapper Light — cream en lugar de blanco

```css
.wrapper-light {
  background-color: var(--color-surface-soft); /* #f5f0e8 — antes: blanco / sin fondo */
}
```

---

### 4.5 Títulos de Sección — Snoop (sin cambios)

`.h-title > h3` y `.a-title > h3` mantienen el gradient text `#212121 → #546E7A`.  
Las decoraciones (línea inferior en `.h-title`, esquinas angulares en `.a-title`) no se modifican.

---

### 4.6 Tags / Badges

#### Badge estándar — cream

```css
.badge {
  background-color: var(--color-surface-card); /* #efe9de — antes: rgba blue-gray */
  color: var(--color-body);
  font-size: 0.75rem;
  font-weight: 500;
  border-radius: 9999px;
  padding: 0.25rem 0.75rem;
}
```

#### Badge primario — rojo Snoop (sin cambios)

```css
.badge-primary {
  background: var(--color-primary); /* #D9261C */
  color: #ffffff;
}
```

---

### 4.7 Tabs / Filtros de categoría

```css
/* Inactivo */
.category-tab {
  background: transparent;
  color: var(--color-body-soft);
  padding: 0.5rem 0.875rem;
  border-radius: var(--radius);
}
/* Activo */
.category-tab.active {
  background-color: var(--color-surface-card); /* #efe9de — antes: #ECEFF1 */
  color: var(--color-body);
}
```

---

### 4.8 Inputs y Formularios — adaptados a cream

```css
.form-control input,
.form-control textarea,
.form-control select {
  background-color: var(--color-canvas);       /* #faf9f5 — antes: #FFFFFF */
  color: var(--color-body);
  border: 1px solid var(--color-hairline);     /* #e6dfd8 */
  border-radius: var(--radius);
  padding: 0.625rem 0.875rem;
  font-family: var(--font-family);
  font-size: 1rem;
  transition: border-color .4s ease;
}
.form-control input:focus {
  border-color: var(--color-primary);          /* #D9261C */
  outline: none;
  box-shadow: 0 0 0 3px rgba(217, 38, 28, 0.12);
}
```

---

### 4.9 Footer — dark navy de Claude (nuevo)

El footer deja de ser implícitamente oscuro para adoptar formalmente el `--color-surface-dark` de Claude, más rico que el implícito de Snoop.

```css
.footer {
  background-color: var(--color-surface-dark); /* #181715 */
  color: var(--color-on-dark-soft);            /* #a09d96 */
  padding: 4rem 0;
}
.footer h5 {
  color: var(--color-on-dark);                 /* #faf9f5 */
  font-style: italic;                          /* mantiene firma Snoop */
}
.footer a {
  color: var(--color-on-dark-soft);
  transition: color .4s ease;
}
.footer a:hover {
  color: var(--color-primary-light);           /* #FF6347 — rojo Snoop claro */
}
.footer .col-4 .block {
  background-color: rgba(37, 35, 32, 0.6);    /* surface-dark-elevated semitransparente */
  border-radius: var(--radius-xxl);
}
.footer .credits {
  color: var(--color-on-dark-soft);
  border-top: 1px solid rgba(250,249,245,0.08);
  padding-top: 1.5rem;
  margin-top: 2rem;
}
```

---

### 4.10 Navegación — Top nav sobre cream

```css
.header .nav-menu a {
  color: var(--color-body);
  font-size: 0.875rem;
  font-weight: 500;
  transition: color .4s ease;
}
.header .nav-menu a:hover,
.header .nav-menu .current-menu-item > a {
  color: var(--color-primary); /* #D9261C */
}
.header .nav-menu .contact > a {
  /* Botón de contacto en la nav */
  background-image: linear-gradient(180deg, #D9261C 0%, #A31810 100%);
  color: #ffffff;
  border-radius: var(--radius);
  padding: 0.375rem 1rem;
}
```

---

## 5\. Ritmo de Superficies por Sección

El sistema alterna entre superficies para crear ritmo visual. Inspirado en la filosofía de pacing de Claude pero con el vocabulario de color de la fusión:

```
Canvas (#faf9f5)       → Hero / Secciones abiertas
Surface Soft (#f5f0e8) → Bandas divisoras sutiles
Surface Card (#efe9de) → Cards, wrapper-light, formularios
Rojo (#D9261C)         → Featured Slogan / Featured Shortcut / CTA
Dark Navy (#181715)    → Footer / Cards de producto / Código
```

**Regla:** no repetir la misma superficie en dos bandas consecutivas.  
**Regla:** el rojo completo es el momento de mayor energía — usarlo una o dos veces por página, nunca en tres bandas seguidas.

---

## 6\. Variables CSS Completas (Standalone)

Para landings HTML independientes, incluir en `:root`:

```css
:root {
  /* === PRIMARIO — ROJO SNOOP === */
  --color-primary:          #D9261C;
  --color-primary-light:    #FF6347;
  --color-primary-dark:     #A31810;
  --color-primary-darker:   #820E0A;
  --color-primary-darkest:  #610906;

  /* === SUPERFICIES — CREAM CLAUDE === */
  --color-canvas:           #faf9f5;  /* fondo de página — reemplaza #FFFFFF */
  --color-surface-soft:     #f5f0e8;  /* bandas sutiles */
  --color-surface-card:     #efe9de;  /* cards y formularios */
  --color-surface-card-strong: #e8e0d2; /* tabs activos */
  --color-surface-dark:     #181715;  /* footer y dark cards */
  --color-surface-dark-elevated: #252320;
  --color-surface-dark-soft: #1f1e1b;

  /* === HAIRLINES SOBRE CREAM === */
  --color-hairline:         #e6dfd8;
  --color-hairline-soft:    #ebe6df;

  /* === TEXTO === */
  --color-body:             #212121;
  --color-body-medium:      #424242;
  --color-body-soft:        #616161;
  --color-on-dark:          #faf9f5;
  --color-on-dark-soft:     #a09d96;
  --color-on-primary:       #ffffff;

  /* === SECUNDARIO — BLUE-GRAY SNOOP === */
  --color-secondary:        #546E7A;
  --color-secondary-light:  #CFD8DC;
  --color-secondary-lighter: #ECEFF1;
  --color-gray-light:       #BDBDBD;
  --color-black:            #000000;

  /* === SEMÁNTICOS === */
  --color-success:          #5db872;
  --color-warning:          #d4a017;
  --color-error:            #c64545;

  /* === TIPOGRAFÍA === */
  --font-display:           'Fraunces', Georgia, serif;   /* H1–H4 */
  --font-body:              'Geist', system-ui, sans-serif; /* body, nav, UI */
  --font-size-sm:           0.75rem;
  --font-size-md:           0.875rem;
  --font-size-base:         1rem;
  --font-size-lg:           1.25rem;
  --font-size-xl:           1.5rem;

  /* === ESPACIADO === */
  --spacing-xs:             0.25rem;
  --spacing-sm:             0.5rem;
  --spacing-md:             0.75rem;
  --spacing-base:           1rem;
  --spacing-lg:             1.25rem;
  --spacing-xl:             1.5rem;
  --spacing-xxl:            3rem;
  --spacing-section:        6rem;    /* nuevo — aire editorial entre bandas */
  --gutter:                 1.5rem;

  /* === BORDER RADIUS === */
  --radius-sm:              0.25rem;
  --radius:                 0.5rem;
  --radius-lg:              1rem;
  --radius-xl:              1.25rem;
  --radius-xxl:             2rem;

  /* === Z-INDEX === */
  --z-sticky:               1020;
  --z-fixed:                1030;

  /* === ALTURAS === */
  --header-height:          5.5rem;
}

/* Fondo de página */
body {
  background-color: var(--color-canvas);
  color: var(--color-body);
  font-family: var(--font-family);
}
```

---

## 7\. Do's y Don'ts

### Do

- Colocar el logo **siempre arriba a la izquierda** del header, alineado verticalmente al centro de la barra de navegación.  
- Usar `logo-snoop-1.svg` (color) sobre fondos claros (canvas, white, surface-card).  
- Usar `logo-snoop-black.svg` con `filter: invert(1) brightness(2)` sobre fondos rojos y dark navy.  
- Mantener el logo en `height: 2rem` en desktop y reducirlo de forma proporcional en mobile (mínimo `1.5rem`).  
- Usar `--color-canvas` (`#faf9f5`) como fondo de página. El blanco puro rompe el tono editorial.  
- Usar **Fraunces** (`--font-display`) para todos los headings H1–H4. Declarar siempre `font-variation-settings` con `opsz` apropiado al tamaño.  
- Mantener el **H1 en upright** (sin itálica) — es la decisión de legibilidad más importante del sistema.  
- Mantener **itálica en H2–H4** y en los gradient titles de `.h-title` / `.a-title` — la itálica se preserva en sub-heads, no desaparece del sistema.  
- Usar **Geist** (`--font-body`) para todo lo que no sea heading: body, nav, botones, labels, captions, inputs.  
- Usar el gradiente rojo `#D9261C → #A31810` en todos los CTAs primarios.  
- Aplicar el patrón asimétrico `2rem 2rem 0.5rem 2rem` en todas las cards.  
- Usar `--color-surface-dark` (`#181715`) para el footer y cualquier sección de código/producto.  
- Alternar superficies entre bandas: canvas → card cream → rojo → dark navy.  
- Añadir `--spacing-section` (6rem) entre bandas principales para dar aire editorial.  
- Usar `.reveal-on` para animar elementos al hacer scroll.

### Don't

- No usar `logo-snoop-1.svg` (color) sobre fondos rojos — el rojo del logo se pierde.  
- No usar `logo-snoop-black.svg` sin filtro sobre fondos oscuros — desaparece.  
- No escalar el logo de forma no proporcional ni usar tamaños menores a `1.5rem` de alto.  
- No desplazar el logo del extremo superior izquierdo salvo en landings especiales con layout centrado.  
- No usar `#FFFFFF` (blanco puro) como fondo de página ni de cards. El blanco plano pierde el carácter de la fusión.  
- No usar IBM Plex Sans — fue reemplazada por Fraunces (display) \+ Geist (UI).  
- No poner el **H1 en itálica** — la legibilidad en titulares largos es la razón central de esta decisión.  
- No omitir `font-variation-settings` en Fraunces — sin `opsz`, los letterforms no se activan y la fuente pierde su carácter diferenciador.  
- No usar Fraunces para cuerpo, nav o botones — solo para headings. El contraste serif/sans es el sistema.  
- No quitar la itálica de **H2–H4** — la itálica sobrevive en sub-heads, no desaparece del sistema.  
- No usar el rojo en más de dos bandas seguidas. Es el momento de energía máxima.  
- No usar un azul brillante o cyan como acento. El blue-gray (`#546E7A`) es el único secundario frío.  
- No introducir sombras pesadas — la elevación viene del contraste entre superficies.  
- No usar `border-radius` fuera del sistema definido.  
- No usar `px` para font-size. Solo `rem`.

---

## 8\. Diferencias Respecto a las Guías Originales

### Qué cambió de Snoop

| Elemento | Antes (Snoop) | Ahora (Híbrido) |
| :---- | :---- | :---- |
| Fondo de página | `#FFFFFF` | `#faf9f5` (canvas cream) |
| Fondo de cards | `rgba(#ECEFF1, 16%)` | `#efe9de` (surface-card) |
| Fondo de formularios | `#FFFFFF` | `#efe9de` (surface-card) |
| Botón secundario | `background: #FFFFFF` | `background: #faf9f5` |
| Hairlines sobre fondo | `#BDBDBD` (gris) | `#e6dfd8` (cream cálido) |
| Footer | Sin token formal | `#181715` (surface-dark) |
| Tabs activos | `#ECEFF1` | `#efe9de` (surface-card) |
| Input focus ring | Sin token | `rgba(217,38,28,0.12)` (rojo al 12%) |
| Espaciado entre secciones | Implícito | `--spacing-section: 6rem` |

### Qué NO cambió de Snoop

- Color primario rojo `#D9261C` y toda la rampa de rojos  
- `font-style: italic` en H2–H4 y en gradient titles — la itálica sobrevive en sub-heads  
- Gradiente de texto en headings (`.h-title`, `.a-title`) — ahora en Fraunces italic  
- Gradiente de botones CTA rojo  
- Patrón de card asimétrico `2rem 2rem 0.5rem 2rem`  
- Sombra de cards `rgba(84,110,122,0.4)`  
- Sistema de grilla de 12 columnas  
- Breakpoints  
- Animaciones `.reveal-on` / pulso  
- Componentes `.button-go`, `.call-to-action`, `.featured-slogan`, `.steps`, `.togglable`  
- Estructura HTML de header, footer y landing pages

### Qué cambió en tipografía (v2 — Fraunces \+ Geist)

| Elemento | v1 | v2 |
| :---- | :---- | :---- |
| H1 familia | IBM Plex Sans | Fraunces (opsz 144, wght 300\) |
| H1 estilo | italic | **normal (upright)** — mejora legibilidad |
| H2–H4 familia | IBM Plex Sans | Fraunces italic (opsz ajustado) |
| Body / nav / UI | IBM Plex Sans | **Geist Variable** |
| Font tokens | `--font-family` único | `--font-display` \+ `--font-body` |

### Qué se tomó de Claude

- Paleta de superficies cream (`#faf9f5`, `#f5f0e8`, `#efe9de`, `#e8e0d2`)  
- Dark navy para footer y product surfaces (`#181715`, `#252320`, `#1f1e1b`)  
- Hairlines cálidos (`#e6dfd8`, `#ebe6df`) en lugar de grises fríos  
- Textos sobre dark (`#faf9f5` / `#a09d96`)  
- Concepto de ritmo alternante entre superficies  
- `--spacing-section: 6rem` como padding explícito entre bandas

---

*Documento v2.1 · Junio 2026 · Fusión Snoop Consulting × Claude Design System · Tipografía Fraunces \+ Geist · Logo top-left \+ variantes por superficie*  
