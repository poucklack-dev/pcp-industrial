document.addEventListener('DOMContentLoaded', () => {
  const token = document.querySelector('meta[name="csrf-token"]')?.content;
  document.querySelectorAll('form[method="post"], form[method="POST"]').forEach(form => {
    if (token && !form.querySelector('input[name="csrf_token"]')) {
      const input = document.createElement('input');
      input.type = 'hidden'; input.name = 'csrf_token'; input.value = token;
      form.appendChild(input);
    }
  });
  const token = document.querySelector('meta[name="csrf-token"]')?.content;
  document.querySelectorAll('form[method="post"], form[method="POST"]').forEach(form => {
    if (token && !form.querySelector('input[name="csrf_token"]')) {
      const input = document.createElement('input');
      input.type = 'hidden'; input.name = 'csrf_token'; input.value = token;
      form.appendChild(input);
    }
  });
  document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => new bootstrap.Tooltip(el));
  document.querySelectorAll('.alert:not(.alert-permanent)').forEach(alert => {
    if (!alert.querySelector('.btn-close')) return;
    window.setTimeout(() => bootstrap.Alert.getOrCreateInstance(alert).close(), 6000);
  });
});

const nativeFetch = window.fetch.bind(window);
window.fetch = (resource, options = {}) => {
  const method = (options.method || 'GET').toUpperCase();
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const token = document.querySelector('meta[name="csrf-token"]')?.content;
    options.headers = new Headers(options.headers || {});
    if (token) options.headers.set('X-CSRFToken', token);
  }
  return nativeFetch(resource, options);
};

const nativeFetch = window.fetch.bind(window);
window.fetch = (resource, options = {}) => {
  const method = (options.method || 'GET').toUpperCase();
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
    const token = document.querySelector('meta[name="csrf-token"]')?.content;
    options.headers = new Headers(options.headers || {});
    if (token) options.headers.set('X-CSRFToken', token);
  }
  return nativeFetch(resource, options);
};
