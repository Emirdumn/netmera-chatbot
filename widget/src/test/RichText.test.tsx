import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RichText } from "../components/RichText";

describe("RichText", () => {
  it("`**...**` isaretlerini kalin metne cevirir, yildizlari gostermez", () => {
    const { container } = render(<RichText text="1. **APNS .p8 Sertifikasi** (Tavsiye edilen)" />);
    expect(screen.getByText("APNS .p8 Sertifikasi").tagName).toBe("STRONG");
    expect(container.textContent).not.toContain("**");
  });

  it("`kod` isaretlerini <code> yapar", () => {
    render(<RichText text="Panelde `Yeni Kampanya` secin" />);
    expect(screen.getByText("Yeni Kampanya").tagName).toBe("CODE");
  });

  it("isaretsiz metni oldugu gibi birakir", () => {
    const { container } = render(<RichText text="Duz bir cumle." />);
    expect(container.textContent).toBe("Duz bir cumle.");
  });

  it("tek basina duran yildizi isaret sanmaz", () => {
    const { container } = render(<RichText text="2 * 3 = 6" />);
    expect(container.textContent).toBe("2 * 3 = 6");
    expect(container.querySelector("strong")).toBeNull();
  });

  it("satir sonlarini korur (pre-wrap ile okunur kalsin)", () => {
    // JSX nitelik dizgesinde `\n` kacis dizisi DEGIL, iki ayri karakterdir —
    // gercek satir sonu icin ifade olarak vermek gerekiyor.
    const { container } = render(<RichText text={"Birinci satir\nIkinci satir"} />);
    expect(container.textContent).toContain("\n");
  });
});
