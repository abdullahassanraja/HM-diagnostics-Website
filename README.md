# HM Diagnostics & Clinics

The latest five-page website for HM Diagnostics & Clinics, Islamabad. This repository contains only the completed version 2 design, served as the main website at `/`.

## Run locally

Install Node.js 18 or newer, then run:

```sh
npm start
```

Open `http://127.0.0.1:4173/`. No package installation or build step is required.

```sh
npm run check
```

## Pages

| Page | Route |
| --- | --- |
| Home | `/` |
| About HM | `/about/` |
| Services | `/services/` |
| Doctors | `/doctors/` |
| Contact and appointment enquiry | `/contact/` |

## Project structure

```text
dist/                 Website source and static hosting directory
  index.html          Home page
  style.css           Shared styles and responsive layouts
  script.js           Navigation, tabs, doctor search and enquiries
  assets/             Local logo and optimized images
  about/index.html
  services/index.html
  doctors/index.html
  contact/index.html
scripts/              Dependency-free local preview and checks
docs/                 Content sources and image generation notes
```

## Included features

- White and powder-blue design with responsive page layouts.
- Shared header and footer navigation.
- Subtle animation, reduced-motion support, and lazy-loaded images.
- Searchable doctor directory with specialty filters.
- Service links that preselect the relevant appointment enquiry.
- A WhatsApp enquiry form. Visitors review and send the message in WhatsApp; it does not confirm or reserve an appointment.
- Click-to-call, email, and Google Maps links.

The proposed AI receptionist has **not** been implemented. No API keys or external AI integrations are included.

## Deploy

Serve **the contents of `dist/` at the website root** using a static host with directory-index support. Assets and navigation use root-relative URLs. A subdirectory deployment, such as a GitHub Pages project URL, requires a base-path adjustment or a custom domain.

## Content and imagery

Clinic facts, doctor names, specialties and contact details come from HM's published website. The clinic must confirm current fees, schedules, preparation instructions and availability. See `docs/content-sources.md`.

Care scenes are fictional AI-generated illustrations featuring Pakistani people. They do not depict the named doctors or actual HM staff, patients or premises. The clinic logo is sourced from the original website. Image generation prompts are included under `docs/`.
