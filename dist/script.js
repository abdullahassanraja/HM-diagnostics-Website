(() => {
  'use strict';
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (!reduced && 'IntersectionObserver' in window) {
    document.documentElement.classList.add('js-motion');
    const observer = new IntersectionObserver(entries => entries.forEach(entry => {
      if (entry.isIntersecting) { entry.target.classList.add('is-visible'); observer.unobserve(entry.target); }
    }), { threshold: 0.06 });
    document.querySelectorAll('.reveal').forEach(node => observer.observe(node));
  }

  const menu = document.querySelector('.menu-toggle');
  const nav = document.querySelector('#main-nav');
  function closeMenu() { nav.classList.remove('is-open'); menu.setAttribute('aria-expanded', 'false'); menu.setAttribute('aria-label', 'Open navigation'); }
  menu.addEventListener('click', () => {
    const open = nav.classList.toggle('is-open');
    menu.setAttribute('aria-expanded', String(open));
    menu.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
  });
  nav.querySelectorAll('a').forEach(link => link.addEventListener('click', closeMenu));
  document.addEventListener('keydown', event => { if (event.key === 'Escape' && nav.classList.contains('is-open')) { closeMenu(); menu.focus(); } });

  // All tab sets support keyboard arrows, Home and End as well as pointer input.
  function setupTabs(container, change) {
    if (!container) return;
    const tabs = [...container.querySelectorAll('[role="tab"]')];
    function select(tab, focus = false) {
      tabs.forEach(item => { const active = item === tab; item.setAttribute('aria-selected', String(active)); item.tabIndex = active ? 0 : -1; });
      change(tab);
      if (focus) tab.focus();
    }
    tabs.forEach((tab, index) => {
      tab.addEventListener('click', () => select(tab));
      tab.addEventListener('keydown', event => {
        let next;
        if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
        if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = tabs.length - 1;
        if (next !== undefined) { event.preventDefault(); select(tabs[next], true); }
      });
    });
  }
  function animateSwap(node) {
    if (reduced) return;
    node.classList.remove('content-swap');
    void node.offsetWidth;
    node.classList.add('content-swap');
  }
  setupTabs(document.querySelector('.about-tabs'), tab => {
    document.querySelectorAll('.about-text [role="tabpanel"]').forEach(panel => { panel.hidden = panel.id !== tab.getAttribute('aria-controls'); });
    animateSwap(document.querySelector('.about-text'));
  });

  const steps = [
    { title: 'Start with a\nconversation.', description: 'Tell us what you need. Our team can help with appointment availability, services, and preparation before you arrive.', list: ['Call or message our clinic team', 'Ask about your test or specialist', 'Confirm your visit and preparation'], image: 'pakistani-consultation.jpg', alt: 'Illustrative consultation between a Pakistani doctor and an older patient', floatTitle: 'You’re in the right place.', floatDetail: 'A friendly team to help you begin', link: 'Speak to our team' },
    { title: 'Care that sees\nthe whole you.', description: 'Visit our clinic for your consultation or diagnostic service. Share your concerns and medical history with your care team.', list: ['Laboratory testing and diagnostic imaging', 'Consultations with qualified specialists', 'Bring your previous reports and prescriptions'], image: 'pakistani-laboratory.jpg', alt: 'Illustrative Pakistani laboratory scientist working with a microscope', floatTitle: 'The right care, together.', floatDetail: 'Diagnostics and specialists in one place', link: 'Ask about your visit' },
    { title: 'Clarity for\nwhat comes next.', description: 'Ask our team about report access, then review your results and follow-up needs with your doctor. Your health story continues.', list: ['Ask when your reports will be available', 'Get help with online report access', 'Discuss the next steps with your doctor'], image: 'pakistani-woman-care.jpg', alt: 'Illustrative Pakistani woman reviewing her care with a female doctor', floatTitle: 'Keep your care moving forward.', floatDetail: 'A clearer understanding of your next step', link: 'Ask about report access' }
  ];
  setupTabs(document.querySelector('.journey-tabs'), tab => {
    const index = Number(tab.dataset.step), step = steps[index];
    const title = document.querySelector('#step-title');
    title.replaceChildren();
    step.title.split('\n').forEach((line, i) => { if (i) title.append(document.createElement('br')); title.append(document.createTextNode(line)); });
    document.querySelector('#step-description').textContent = step.description;
    document.querySelector('#step-badge').textContent = 'STEP 0' + (index + 1);
    document.querySelector('#step-list').replaceChildren(...step.list.map(text => { const li = document.createElement('li'); li.textContent = text; return li; }));
    const photo = document.querySelector('#step-image'); photo.src = 'assets/' + step.image; photo.alt = step.alt;
    document.querySelector('#step-float-title').textContent = step.floatTitle;
    document.querySelector('#step-float-detail').textContent = step.floatDetail;
    const link = document.querySelector('#step-link'); link.replaceChildren(document.createTextNode(step.link + ' ')); const arrow = document.createElement('span'); arrow.textContent = '↗'; link.append(arrow);
    document.querySelector('#step-count').textContent = '0' + (index + 1) + ' / 03';
    document.querySelector('.counter-track i').style.width = ((index + 1) / 3 * 100) + '%';
    document.querySelector('#journey-panel').setAttribute('aria-labelledby', tab.id);
    animateSwap(document.querySelector('.journey-main'));
  });

  const categories = {
    diagnostics: { image: 'pakistani-laboratory.jpg', alt: 'Illustrative Pakistani laboratory scientist at work', caption: 'A closer look.\nA clearer picture.', items: [['Laboratory testing', 'Diagnostic testing to support your doctor’s assessment.'], ['MRI & CT scan', 'Diagnostic imaging for a more detailed view.'], ['Ultrasound & digital X-ray', 'Imaging services, together at our clinic.'], ['ECHO, ECG & ETT', 'Cardiac investigations for your heart health.']] },
    specialists: { image: 'pakistani-consultation.jpg', alt: 'Illustrative Pakistani doctor consulting with an older patient', caption: 'Expertise, with\na human touch.', items: [['Cardiology & general medicine', 'Specialist consultations for your ongoing health needs.'], ['Women’s & children’s health', 'Gynecology and child specialist consultations.'], ['Dermatology, ENT & gastroenterology', 'Focused expertise for your particular concern.'], ['More specialist clinics', 'Orthopedics, urology, pulmonology, psychiatry, and more.']] },
    support: { image: 'pakistani-woman-care.jpg', alt: 'Illustrative Pakistani patient speaking with a doctor', caption: 'Care beyond\nthe first visit.', items: [['Physiotherapy', 'Rehabilitation support for movement and recovery.'], ['Hearing center', 'A dedicated service for hearing concerns.'], ['Pharmacy', 'Pharmacy support, available at the clinic.'], ['Endoscopy & NCS', 'Additional diagnostic services for specialist assessment.']] }
  };
  setupTabs(document.querySelector('.service-filters'), tab => {
    const category = categories[tab.dataset.category];
    const image = document.querySelector('#services-image'); image.src = 'assets/' + category.image; image.alt = category.alt;
    const caption = document.querySelector('#services-photo-title'); caption.replaceChildren();
    category.caption.split('\n').forEach((line, i) => { if (i) caption.append(document.createElement('br')); caption.append(document.createTextNode(line)); });
    document.querySelector('#service-options').replaceChildren(...category.items.map(([name, description], index) => {
      const link = document.createElement('a'); link.href = 'https://wa.me/923346333044?text=' + encodeURIComponent('Hello HM, I would like to ask about ' + name + '.'); link.target = '_blank'; link.rel = 'noopener';
      const number = document.createElement('span'); number.textContent = '0' + (index + 1);
      const content = document.createElement('div'), title = document.createElement('h3'), text = document.createElement('p'), arrow = document.createElement('b');
      title.textContent = name; text.textContent = description; arrow.textContent = '↗'; content.append(title, text); link.append(number, content, arrow); return link;
    }));
    document.querySelector('#services-panel').setAttribute('aria-labelledby', tab.id);
    animateSwap(document.querySelector('#services-panel'));
  });

  const doctorSearch = document.querySelector('#doctor-search');
  if (doctorSearch) {
    const specialty = document.querySelector('#doctor-specialty');
    const cards = [...document.querySelectorAll('[data-doctor]')];
    const updateDirectory = () => {
      const query = doctorSearch.value.trim().toLocaleLowerCase();
      let count = 0;
      cards.forEach(card => {
        const visible = (!query || card.dataset.doctor.includes(query)) && (!specialty.value || card.dataset.specialty === specialty.value);
        card.hidden = !visible;
        if (visible) { count++; card.classList.add('is-visible'); }
      });
      document.querySelector('#doctor-count').textContent = count + (count === 1 ? ' specialist listed' : ' specialists listed');
      document.querySelector('#doctor-empty').hidden = count !== 0;
    };
    doctorSearch.addEventListener('input', updateDirectory);
    specialty.addEventListener('change', updateDirectory);
    document.querySelector('#doctor-reset').addEventListener('click', () => { doctorSearch.value = ''; specialty.value = ''; updateDirectory(); doctorSearch.focus(); });
  }

  const enquiryForm = document.querySelector('#appointment-form');
  if (enquiryForm) {
    const service = document.querySelector('#enquiry-service');
    const doctor = document.querySelector('#enquiry-doctor');
    const date = document.querySelector('#enquiry-date');
    const parameters = new URLSearchParams(location.search);
    const requestedService = parameters.get('service');
    const requestedDoctor = parameters.get('doctor');
    if (requestedService && requestedService.length < 150) {
      const match = [...service.options].find(option => option.value === requestedService);
      if (match) service.value = match.value;
      else {
        const option = document.createElement('option'); option.value = requestedService; option.textContent = requestedService;
        service.append(option); service.value = requestedService;
      }
    }
    if (requestedDoctor && [...doctor.options].some(option => option.value === requestedDoctor)) {
      doctor.value = requestedDoctor;
      service.value = 'Specialist consultation';
    }
    const today = new Date();
    date.min = [today.getFullYear(), String(today.getMonth() + 1).padStart(2, '0'), String(today.getDate()).padStart(2, '0')].join('-');
    enquiryForm.addEventListener('submit', event => {
      event.preventDefault();
      if (!enquiryForm.reportValidity()) return;
      const lines = ['Hello HM Diagnostics & Clinics, I would like to enquire about an appointment.', 'Service: ' + service.value];
      if (doctor.value) lines.push('Preferred doctor: ' + doctor.value);
      if (date.value) lines.push('Preferred date: ' + date.value);
      lines.push('Please let me know the availability, fees, and any preparation required.');
      const link = document.createElement('a');
      link.href = 'https://wa.me/923346333044?text=' + encodeURIComponent(lines.join('\n'));
      link.target = '_blank'; link.rel = 'noopener';
      document.querySelector('#enquiry-status').replaceChildren(document.createTextNode('Your enquiry is ready. '));
      const review = link.cloneNode(); review.textContent = 'Open or review it in WhatsApp ↗';
      document.querySelector('#enquiry-status').append(review);
      link.click();
    });
  }

  // Native lazy loading keeps the hero immediate and defers images further down the page.
  // Gentle desktop easing is optional; keyboard, touch, zoom and reduced motion stay native.
  if (!reduced && matchMedia('(pointer: fine)').matches) {
    let target = scrollY, frame = 0;
    const stop = () => { cancelAnimationFrame(frame); frame = 0; target = scrollY; };
    const animate = () => {
      const max = document.documentElement.scrollHeight - innerHeight;
      target = Math.max(0, Math.min(max, target));
      const delta = target - scrollY;
      if (Math.abs(delta) < 0.7) { frame = 0; return; }
      window.scrollTo({ top: scrollY + delta * 0.14, behavior: 'instant' });
      frame = requestAnimationFrame(animate);
    };
    addEventListener('wheel', event => {
      if (event.ctrlKey || event.metaKey || event.deltaMode !== 0 || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
      if (event.target.closest('[role="tablist"]')) return;
      event.preventDefault(); if (!frame) target = scrollY;
      target += event.deltaY;
      if (!frame) frame = requestAnimationFrame(animate);
    }, { passive: false });
    addEventListener('keydown', event => { if (['ArrowDown', 'ArrowUp', 'PageDown', 'PageUp', 'Home', 'End', ' '].includes(event.key)) stop(); });
    addEventListener('pointerdown', stop);
    addEventListener('touchstart', stop, { passive: true });
    document.querySelectorAll('a[href^="#"]').forEach(link => link.addEventListener('click', stop));
  }
})();
