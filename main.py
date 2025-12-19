import fitz  # PyMuPDF
import argparse
import math
from enum import StrEnum

# Where
class CutLocation(StrEnum):
    FRONT = 'front'
    BACK = 'back'
    NONE = 'none'
    BOTH = 'both'

    def front(self) -> bool:
        return self == CutLocation.BOTH or self == CutLocation.FRONT

    def back(self) -> bool:
        return self == CutLocation.BOTH or self == CutLocation.BACK

def draw_cut_outline(page: fitz.Page, rect: fitz.Rect) -> None:
    lines = [
        (fitz.Point(rect.x0, rect.y0), fitz.Point(rect.x1, rect.y0)), # top
        (fitz.Point(rect.x0, rect.y1), fitz.Point(rect.x1, rect.y1)), # bottom
        (fitz.Point(rect.x0, rect.y0), fitz.Point(rect.x0, rect.y1)), # left
        (fitz.Point(rect.x1, rect.y0), fitz.Point(rect.x1, rect.y1)), # right
    ]
    for line in lines:
        p1, p2 = line
        page.draw_line(p1, p2,
           color=(0, 0, 0), # black
           stroke_opacity=0.1, # grey
           width=0.5,
           dashes="[1 12]"
       )


def main():
    parser = argparse.ArgumentParser(description="Create a print-ready PDF grid of flashcards from an input PDF.")
    parser.add_argument("input", help="Path to the input PDF file.")
    parser.add_argument("output", help="Path to the output PDF file.")
    parser.add_argument("--width", type=float, default=None, help="Paper width in inches (override).")
    parser.add_argument("--height", type=float, default=None, help="Paper height in inches (override).")
    parser.add_argument("--margin", type=float, default=0.25, help="Margin in inches.")
    # parser.add_argument("--no-cut-lines", type=bool, default=False, help="Remove lines for cutting")
    parser.add_argument("--lines", type=CutLocation, default=CutLocation.FRONT, help=f"Where to place cut-lines (if any): {', '.join([a.value for a in CutLocation])}", choices=list(CutLocation))
    parser.add_argument("--flip-back", action="store_true", help="Rotate every second sheet by 180° for duplex printing")

    args = parser.parse_args()

    doc = fitz.open(args.input)
    num_pages = len(doc)
    if num_pages % 2 != 0:
        raise ValueError("Input PDF must have an even number of pages.")

    num_cards = num_pages // 2
    card_rect = doc[0].rect
    card_w = card_rect.width
    card_h = card_rect.height

    margin_pt = args.margin * 72

    if args.width is None and args.height is None:
        # Default to 8.5x11, infer orientation
        port_w = 8.5 * 72
        port_h = 11 * 72
        port_print_w = port_w - 2 * margin_pt
        port_print_h = port_h - 2 * margin_pt
        port_cols = math.floor(port_print_w / card_w)
        port_rows = math.floor(port_print_h / card_h)
        port_fit = port_cols * port_rows

        land_w = 11 * 72
        land_h = 8.5 * 72
        land_print_w = land_w - 2 * margin_pt
        land_print_h = land_h - 2 * margin_pt
        land_cols = math.floor(land_print_w / card_w)
        land_rows = math.floor(land_print_h / card_h)
        land_fit = land_cols * land_rows

        if land_fit > port_fit:
            paper_w = land_w
            paper_h = land_h
            cols = land_cols
            rows = land_rows
        else:
            paper_w = port_w
            paper_h = port_h
            cols = port_cols
            rows = port_rows
    else:
        if args.width is None or args.height is None:
            raise ValueError("Must specify both --width and --height if overriding.")
        paper_w = args.width * 72
        paper_h = args.height * 72
        print_w = paper_w - 2 * margin_pt
        print_h = paper_h - 2 * margin_pt
        cols = math.floor(print_w / card_w)
        rows = math.floor(print_h / card_h)

    if rows == 0 or cols == 0:
        raise ValueError("Flashcards do not fit on the specified paper size with given margins.")


    # Calculate extra width following each row (for when it is not an exact fit), to put before each row of every back page
    print_w = paper_w - 2 * margin_pt
    print_h = paper_h - 2 * margin_pt
    extra_width = math.remainder(print_w, card_w)

    cards_per_page = rows * cols

    fronts_list = [doc[i] for i in range(0, num_pages, 2)]
    backs_list = [doc[i] for i in range(1, num_pages, 2)]

    new_doc = fitz.open()

    for start in range(0, num_cards, cards_per_page):
        chunk_fronts = fronts_list[start:start + cards_per_page]
        chunk_backs = backs_list[start:start + cards_per_page]

        # Create front page
        front_page = new_doc.new_page(width=paper_w, height=paper_h)
        for r in range(rows):
            row_fronts = chunk_fronts[r * cols:(r + 1) * cols]
            for c in range(cols):
                if c >= len(row_fronts):
                    break
                x0 = margin_pt + c * card_w
                y0 = margin_pt + r * card_h
                rect = fitz.Rect(x0, y0, x0 + card_w, y0 + card_h)
                front_page.show_pdf_page(rect, doc, row_fronts[c].number)
                if args.lines.front():
                    draw_cut_outline(front_page, rect)

        # Create back page with mirrored order (reverse columns) and right-aligned for partial rows
        back_page = new_doc.new_page(width=paper_w, height=paper_h)
        for r in range(rows):
            row_backs = chunk_backs[r * cols:(r + 1) * cols][::-1]
            k = len(row_backs)
            offset = cols - k
            for i in range(k):
                c = offset + i
                x0 = (margin_pt + c * card_w) + extra_width
                y0 = margin_pt + r * card_h
                rect = fitz.Rect(x0, y0, x0 + card_w, y0 + card_h)
                back_page.show_pdf_page(rect, doc, row_backs[i].number)
                if args.lines.back():
                    draw_cut_outline(back_page, rect)
        if args.flip_back:
            back_page.set_rotation(180)

    new_doc.save(args.output)
    new_doc.close()
    doc.close()

if __name__ == "__main__":
    main()
