/** Kullaniciya gorunen TUM metinler burada (guardrail 5: koda gomulu metin yok).
 *
 * a11y etiketleri de burada — spec'te `a11y.panelAriaLabel` gibi degerler
 * token olarak duruyor ama bunlar metin, token degil; ceviri gerektiginde
 * buradan yonetilir.
 */
export const strings = {
  launcher: {
    open: "Destek sohbetini aç",
    close: "Destek sohbetini kapat",
    unreadSuffix: "okunmamış mesaj",
  },
  panel: {
    ariaLabel: "Destek",
    close: "Kapat",
    back: "Geri",
  },
  tabs: {
    home: "Ana sayfa",
    messages: "Mesajlar",
    help: "Yardım",
  },
  home: {
    greeting: "Merhaba 👋",
    subtitle: "Netmera hakkında ne sormak istersiniz?",
    startConversation: "Sohbet başlat",
    continueConversation: "Sohbete devam et",
    recentTitle: "Son sohbetiniz",
    searchPlaceholder: "Yardım konularında ara",
  },
  messages: {
    title: "Mesajlar",
    empty: "Henüz bir sohbetiniz yok.",
    emptyAction: "İlk sohbeti başlat",
    you: "Siz",
    bot: "Netmera Asistan",
    staffFallback: "Müşteri Temsilcisi",
  },
  conversation: {
    typing: "yazıyor",
    waitingForHuman: "Bir temsilciye aktarılıyorsunuz…",
    continueWithBot: "Bot ile devam et",
    sources: "Kaynaklar",
  },
  composer: {
    placeholder: "Mesajınızı yazın…",
    send: "Gönder",
    emailLabel: "E-posta adresiniz",
    emailPlaceholder: "ornek@sirket.com",
    emailHint: "Size dönebilmemiz için e-posta adresinizi alalım.",
    emailInvalid: "Geçerli bir e-posta adresi girin.",
  },
  help: {
    title: "Yardım",
    searchPlaceholder: "Bir konu arayın",
    empty: "Aramanızla eşleşen bir başlık bulunamadı.",
    articlesTitle: "Popüler başlıklar",
    readMore: "Devamını oku",
  },
  error: {
    title: "Bir şeyler ters gitti",
    body: "Bağlantı kurulamadı. Lütfen tekrar deneyin.",
    retry: "Tekrar dene",
  },
  loading: {
    label: "Yükleniyor",
  },
} as const;

export type Strings = typeof strings;
