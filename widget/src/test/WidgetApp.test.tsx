/** AŞAMA 5 — etkilesim ve erisilebilirlik testleri.
 *
 * Transport MOCK'lanmis; hicbir ag cagrisi yok. Kabul kriteri:
 * "Transport mock'layarak tum UI durumlari testle uretilebiliyor."
 */
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it } from "vitest";
import { WidgetApp } from "../WidgetApp";
import { createMockTransport } from "../ports/mockTransport";
import type { ChatTransport } from "../ports/types";
import { strings } from "../strings";
import type { WidgetConfig } from "../ports/types";
import { mockMessages } from "../mock/fixtures";

const config: WidgetConfig = {
  apiBaseUrl: "mock://",
  defaultOpen: false,
  pollIntervalMs: 0,
};

function renderWidget(transport: ChatTransport = createMockTransport({ messages: [] })) {
  return {
    user: userEvent.setup(),
    ...render(<WidgetApp transport={transport} config={config} />),
  };
}

/** Panel elemani.
 *
 * getByRole KULLANILMIYOR: panel kapaliyken aria-hidden="true" oldugu icin
 * erisilebilirlik agacindan cikiyor ve rol sorgusuyla bulunamiyor. Testin
 * amaci zaten tam olarak o niteligi (aria-hidden / inert) dogrulamak,
 * bu yuzden dogrudan DOM'dan aliyoruz.
 */
function panel(): HTMLElement {
  const el = document.querySelector<HTMLElement>(
    `section[aria-label="${strings.panel.ariaLabel}"]`,
  );
  if (!el) throw new Error("Panel elemani bulunamadi");
  return el;
}

beforeEach(() => {
  window.localStorage.clear();
});

describe("acma / kapama", () => {
  it("launcher panele acar ve kapatir", async () => {
    const { user } = renderWidget();

    expect(panel()).toHaveAttribute("aria-hidden", "true");

    await user.click(screen.getByRole("button", { name: strings.launcher.open }));
    expect(panel()).toHaveAttribute("aria-hidden", "false");

    await user.click(screen.getByRole("button", { name: strings.launcher.close }));
    expect(panel()).toHaveAttribute("aria-hidden", "true");
  });

  it("basliktaki kapat butonu paneli kapatir", async () => {
    const { user } = renderWidget();
    await user.click(screen.getByRole("button", { name: strings.launcher.open }));

    await user.click(screen.getByRole("button", { name: strings.panel.close }));
    expect(panel()).toHaveAttribute("aria-hidden", "true");
  });

  it("acik/kapali durumu localStorage'a yaziliyor", async () => {
    const { user } = renderWidget();
    await user.click(screen.getByRole("button", { name: strings.launcher.open }));
    await waitFor(() => expect(window.localStorage.getItem("netmera.widget.open")).toBe("1"));
  });
});

describe("sekme gecisi", () => {
  it("sekmeler arasi gecis yapar ve aria-selected gunceller", async () => {
    const { user } = renderWidget();
    await user.click(screen.getByRole("button", { name: strings.launcher.open }));

    const home = screen.getByRole("tab", { name: strings.tabs.home });
    const help = screen.getByRole("tab", { name: strings.tabs.help });

    expect(home).toHaveAttribute("aria-selected", "true");

    await user.click(help);
    expect(help).toHaveAttribute("aria-selected", "true");
    expect(home).toHaveAttribute("aria-selected", "false");

    // Yardim sekmesi arama alanini gostermeli
    expect(screen.getByPlaceholderText(strings.help.searchPlaceholder)).toBeInTheDocument();
    // Bos sorguda populer makaleler gelsin
    expect(
      await screen.findByRole("button", { name: /iOS SDK entegrasyonu/i }),
    ).toBeInTheDocument();
  });
});

describe("RAG kaynaklari", () => {
  it("kaynak tiklaninca panelde makale acilir", async () => {
    const transport = createMockTransport({ messages: mockMessages });
    const { user } = renderWidget(transport);
    await user.click(screen.getByRole("button", { name: strings.launcher.open }));
    await user.click(screen.getByRole("button", { name: strings.home.startConversation }));

    const source = await screen.findByRole("button", { name: /iOS SDK Kurulumu/i });
    await user.click(source);

    expect(
      await screen.findByText(/CocoaPods ya da Swift Package Manager/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: strings.help.readMore })).toHaveAttribute(
      "href",
      "https://user.netmera.com/netmera-developer-guide/ios",
    );
  });
});

describe("mesaj gonderme", () => {
  it("mesaj gonderir ve bot cevabini gosterir (transport mock)", async () => {
    const { user } = renderWidget();
    await user.click(screen.getByRole("button", { name: strings.launcher.open }));
    await user.click(screen.getByRole("button", { name: strings.home.startConversation }));

    const input = screen.getByPlaceholderText(strings.composer.placeholder);
    await user.type(input, "Netmera nedir?");
    await user.keyboard("{Enter}");

    expect(await screen.findByText("Netmera nedir?")).toBeInTheDocument();
    expect(await screen.findByText(/mock cevap/i)).toBeInTheDocument();
    // Gonderim sonrasi taslak temizlenmeli
    await waitFor(() => expect(input).toHaveValue(""));
  });

  it("Shift+Enter satir ekler, gondermez", async () => {
    const { user } = renderWidget();
    await user.click(screen.getByRole("button", { name: strings.launcher.open }));
    await user.click(screen.getByRole("button", { name: strings.home.startConversation }));

    const input = screen.getByPlaceholderText(strings.composer.placeholder);
    await user.type(input, "birinci");
    await user.keyboard("{Shift>}{Enter}{/Shift}");
    await user.type(input, "ikinci");

    expect(input).toHaveValue("birinci\nikinci");
    // Hicbir mesaj gonderilmemis olmali
    expect(screen.queryByText(/mock cevap/i)).not.toBeInTheDocument();
  });

  it("bos mesaj gonderilemez", async () => {
    const { user } = renderWidget();
    await user.click(screen.getByRole("button", { name: strings.launcher.open }));
    await user.click(screen.getByRole("button", { name: strings.home.startConversation }));

    expect(screen.getByRole("button", { name: strings.composer.send })).toBeDisabled();
  });
});

describe("hata ve yeniden dene", () => {
  it("transport hata verirse hata durumu ve tekrar dene gorunur", async () => {
    const failing = createMockTransport({ failing: true });
    const { user } = renderWidget(failing);

    await user.click(screen.getByRole("button", { name: strings.launcher.open }));

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByText(strings.error.title)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: strings.error.retry })).toBeInTheDocument();
  });
});

describe("devir akisi", () => {
  it("devir sonrasi e-posta alani cikar ve gecersiz e-posta reddedilir", async () => {
    const { user } = renderWidget();
    await user.click(screen.getByRole("button", { name: strings.launcher.open }));
    await user.click(screen.getByRole("button", { name: strings.home.startConversation }));

    const input = screen.getByPlaceholderText(strings.composer.placeholder);
    await user.type(input, "temsilci istiyorum");
    await user.keyboard("{Enter}");

    // E-posta alani gorunmeli
    const emailField = await screen.findByLabelText(strings.composer.emailLabel);

    await user.type(emailField, "gecersiz");
    await user.keyboard("{Enter}");
    expect(await screen.findByText(strings.composer.emailInvalid)).toBeInTheDocument();

    // Gecerli e-posta -> form kapanir
    await user.clear(emailField);
    await user.type(emailField, "ali@example.com");
    await user.keyboard("{Enter}");

    await waitFor(() =>
      expect(screen.queryByLabelText(strings.composer.emailLabel)).not.toBeInTheDocument(),
    );
  });

  it("'bot ile devam et' bekleme durumunu kaldirir", async () => {
    const { user } = renderWidget();
    await user.click(screen.getByRole("button", { name: strings.launcher.open }));
    await user.click(screen.getByRole("button", { name: strings.home.startConversation }));

    await user.type(
      screen.getByPlaceholderText(strings.composer.placeholder),
      "temsilci istiyorum",
    );
    await user.keyboard("{Enter}");

    const resume = await screen.findByRole("button", {
      name: strings.conversation.continueWithBot,
    });
    await user.click(resume);

    await waitFor(() =>
      expect(
        screen.queryByRole("button", { name: strings.conversation.continueWithBot }),
      ).not.toBeInTheDocument(),
    );
  });
});

describe("erisilebilirlik", () => {
  it("Esc paneli kapatir", async () => {
    const { user } = renderWidget();
    await user.click(screen.getByRole("button", { name: strings.launcher.open }));
    expect(panel()).toHaveAttribute("aria-hidden", "false");

    await user.keyboard("{Escape}");
    expect(panel()).toHaveAttribute("aria-hidden", "true");
  });

  it("panel kapaninca odak launcher'a doner", async () => {
    const { user } = renderWidget();
    const launcher = screen.getByRole("button", { name: strings.launcher.open });
    await user.click(launcher);

    await user.keyboard("{Escape}");

    await waitFor(() =>
      expect(screen.getByRole("button", { name: strings.launcher.open })).toHaveFocus(),
    );
  });

  it("panel acikken odak icinde hapsolur (focus trap)", async () => {
    const { user } = renderWidget();
    await user.click(screen.getByRole("button", { name: strings.launcher.open }));

    const region = panel();
    const focusables = within(region).getAllByRole("button");
    const last = focusables[focusables.length - 1];

    last.focus();
    expect(last).toHaveFocus();

    // Son elemandan Tab -> ilk elemana donmeli, panelin disina cikmamali
    await user.tab();
    await waitFor(() => expect(region.contains(document.activeElement)).toBe(true));
  });

  it("mesaj listesi ekran okuyucuya canli bildiriliyor", async () => {
    const { user } = renderWidget();
    await user.click(screen.getByRole("button", { name: strings.launcher.open }));
    await user.click(screen.getByRole("button", { name: strings.home.startConversation }));

    const log = screen.getByRole("log");
    expect(log).toHaveAttribute("aria-live", "polite");
  });

  it("panel kapaliyken icerik klavye sirasindan cikarilir", () => {
    renderWidget();
    expect(panel()).toHaveAttribute("inert");
  });
});
