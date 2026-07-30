/** Demo/test verisi. Gercek icerik gibi gorunmesi icin Netmera alanindan
 *  yazildi — lorem ipsum yok. AŞAMA 3'te bunun yerini gercek transport alacak. */
import type { Article, Conversation, Message } from "../types";

const minutesAgo = (n: number) => new Date(Date.now() - n * 60_000).toISOString();

export const mockMessages: Message[] = [
  {
    id: "m1",
    author: "user",
    text: "Merhaba, iOS uygulamamıza push bildirim entegrasyonu yapmak istiyoruz. Nereden başlamalıyız?",
    sentAt: minutesAgo(12),
  },
  {
    id: "m2",
    author: "bot",
    authorName: "Netmera Asistan",
    text: "Merhaba! iOS SDK entegrasyonu için önce Netmera panelinden uygulamanızı oluşturup APNs sertifikanızı yüklemeniz gerekiyor. Ardından SDK'yı CocoaPods veya Swift Package Manager ile projenize ekleyip AppDelegate içinde başlatıyorsunuz.",
    sentAt: minutesAgo(11),
    sources: [
      {
        title: "iOS SDK Kurulumu",
        url: "https://user.netmera.com/netmera-developer-guide/ios",
      },
      {
        title: "APNs Sertifikası Yükleme",
        url: "https://user.netmera.com/netmera-user-guide/push-notifications",
      },
    ],
  },
  {
    id: "m3",
    author: "user",
    text: "Peki Swift Package Manager ile kurarken minimum iOS sürümü kaç olmalı?",
    sentAt: minutesAgo(6),
  },
];

export const mockLongMessage: Message = {
  id: "m-long",
  author: "bot",
  authorName: "Netmera Asistan",
  text: `Segment oluşturmak için panelde Targeting > Segments adımını izleyin. Segmentler üç ana kritere göre kurulabilir:

1. Kullanıcı özellikleri — cihaz dili, ülke, uygulama sürümü, özel tanımladığınız profil alanları.
2. Davranış — belirli bir olayı (event) kaç kez ve hangi zaman aralığında gerçekleştirdiği.
3. Etkileşim — daha önce gönderilmiş kampanyaları açma, tıklama veya yok sayma davranışı.

Segment kaydedildikten sonra kampanya oluştururken hedef kitle olarak seçebilirsiniz. Segmentler dinamiktir: kriterlere uyan kullanıcılar zaman içinde otomatik olarak segmente girer ve çıkar, bu yüzden kampanya gönderim anında yeniden hesaplanır.

Çok uzun bir bağlantı örneği de burada taşma davranışını görmek için duruyor: https://user.netmera.com/netmera-user-guide/audience/segments/creating-a-new-segment-with-behavioural-criteria`,
  sentAt: minutesAgo(2),
  sources: [
    {
      title: "Segment Oluşturma",
      url: "https://user.netmera.com/netmera-user-guide/audience/segments",
    },
  ],
};

export const mockConversations: Conversation[] = [
  {
    id: "c1",
    preview: "Peki Swift Package Manager ile kurarken minimum iOS sürümü kaç olmalı?",
    lastMessageAt: minutesAgo(6),
    unreadCount: 0,
    waitingForHuman: false,
    messages: mockMessages,
  },
  {
    id: "c2",
    preview: "Fiyatlandırma paketleri hakkında bilgi alabilir miyim?",
    lastMessageAt: minutesAgo(140),
    unreadCount: 2,
    waitingForHuman: true,
    messages: [
      {
        id: "m4",
        author: "user",
        text: "Fiyatlandırma paketleri hakkında bilgi alabilir miyim?",
        sentAt: minutesAgo(145),
      },
      {
        id: "m5",
        author: "staff",
        authorName: "Ayşe Kaya",
        text: "Merhaba, satış ekibinden Ayşe. Kullanıcı sayınıza göre bir teklif hazırlayabilirim.",
        sentAt: minutesAgo(140),
      },
    ],
  },
];

export const mockArticles: Article[] = [
  {
    id: "a1",
    title: "iOS SDK entegrasyonu nasıl yapılır?",
    excerpt:
      "CocoaPods veya Swift Package Manager ile SDK kurulumu, APNs sertifikası ve AppDelegate yapılandırması.",
    url: "https://user.netmera.com/netmera-developer-guide/ios",
    body: [
      "Netmera iOS SDK'sını projenize CocoaPods ya da Swift Package Manager ile ekleyebilirsiniz. CocoaPods kullanıyorsanız Podfile dosyanıza Netmera pod'unu ekleyip pod install komutunu çalıştırın.",
      "Kurulumdan sonra Netmera panelinden aldığınız API anahtarını AppDelegate içindeki başlatma çağrısına verin. Bu çağrı uygulama açılışında bir kez çalışmalıdır.",
      "Push bildirimlerinin çalışması için Apple Developer hesabınızdan bir APNs anahtarı oluşturup Netmera paneline yüklemeniz gerekir. Anahtar yüklenmeden gönderimler cihaza ulaşmaz.",
    ],
  },
  {
    id: "a2",
    title: "Segment nasıl oluşturulur?",
    excerpt:
      "Kullanıcı özellikleri, davranış ve kampanya etkileşimine göre dinamik hedef kitle tanımlama.",
    url: "https://user.netmera.com/netmera-user-guide/audience/segments",
    body: [
      "Segmentler, kampanyalarınızı doğru kitleye göndermenizi sağlayan dinamik kullanıcı gruplarıdır. Panelde Targeting bölümünden oluşturulur.",
      "Bir segment; profil özellikleri, gerçekleştirilen olaylar ve geçmiş kampanya etkileşimleri gibi kriterlerin birleşimiyle tanımlanabilir.",
      "Segmentler dinamiktir. Kriterlere uyan kullanıcılar otomatik olarak segmente girer, uymayanlar çıkar; gönderim anında liste yeniden hesaplanır.",
    ],
  },
  {
    id: "a3",
    title: "Netmera nedir?",
    excerpt:
      "Mobil ve web uygulamaları için müşteri etkileşim ve pazarlama otomasyonu platformu.",
    url: "https://www.netmera.com",
    body: [
      "Netmera; mobil ve web uygulamaları için push bildirim, e-posta, SMS ve uygulama içi mesaj gönderimini tek panelden yönetmenizi sağlayan bir müşteri etkileşim platformudur.",
      "Kullanıcı davranışlarını analiz ederek segmentler oluşturabilir, bu segmentlere otomatik akışlar (journey) kurabilirsiniz.",
    ],
  },
];
