import "@testing-library/jest-dom/vitest";

/** jsdom bazi tarayici API'lerini saglamiyor; testler patlamasin diye
 *  en azindan var olmalarini sagliyoruz. */
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia;
}

// scrollTo/scrollHeight jsdom'da yok — auto-scroll efekti patlamasin.
if (!Element.prototype.scrollTo) {
  Element.prototype.scrollTo = () => {};
}
