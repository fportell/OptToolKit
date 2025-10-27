## Frontend Style Description

**Framework & Layout:**

- Uses `Bootstrap 5` as the primary UI framework.
- Layout is responsive, clean, and inspired by government web design (but **not** using the Government of Canada Design System).
- EJS templates are used for server-side rendering.

**Color Palette:**

- Relies on Bootstrap 5’s default palette, which includes:
    - **Primary:** #0d6efd (blue)
    - **Secondary:** #6c757d (gray)
    - **Success:** #198754 (green)
    - **Danger:** #dc3545 (red)
    - **Warning:** #ffc107 (yellow)
    - **Info:** #0dcaf0 (cyan)
    - **Light:** #f8f9fa (off-white)
    - **Dark:** #212529 (almost black)
- The overall look is neutral, professional, and accessible, with high contrast for readability.

**Typography:**

- Uses Bootstrap’s default system font stack for clarity and accessibility.
- Headings and buttons are bold and clear.

**Components & UI Elements:**

- Navigation bar, cards, tables, forms, and modals all use Bootstrap 5 components.
- Buttons and alerts use Bootstrap’s color classes for consistency.
- Pagination, tooltips, and flash messages are styled with Bootstrap utilities.

**Other Style Notes:**

- Minimal custom CSS (`/legacy_code/rss-manager/public/css/main.css`)—mostly for minor tweaks or spacing.
- No heavy branding or custom graphics; focus is on usability and clarity.
- UI text is English-only.
- Icons (if used) are likely from Bootstrap Icons or similar.

---

**Summary:**  
The frontend style is modern, clean, and functional, leveraging Bootstrap 5’s default palette and components for a government-inspired, accessible look. The palette is blue/gray-centric, with accent colors for status and actions, and minimal custom styling.

If you want to extract the exact palette or see the CSS, check `/legacy_code/rss-manager/public/css/main.css` or the Bootstrap 5 documentation for color variables.
