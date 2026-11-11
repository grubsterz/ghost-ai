from __future__ import annotations

from PySide6.QtWidgets import QHBoxLayout

from ... import __version__
from ...i18n import tr
from ..widgets import Card, Page, button, label, open_url


class AboutPage(Page):
    def __init__(self, ctx) -> None:
        super().__init__(tr("about.title"))
        links = ctx.config.links
        main = Card()
        main.lay.addWidget(label("GHOST AI", "Big"))
        main.lay.addWidget(label(tr("about.version", v=__version__), "Muted"))
        main.lay.addWidget(label(tr("about.text")))
        row = QHBoxLayout()
        row.addWidget(button(tr("about.website"), "Primary", lambda: open_url(links.website), links.website))
        if links.source and links.source != links.website:
            row.addWidget(button(tr("about.source"), slot=lambda: open_url(links.source), tip=links.source))
        row.addStretch(1)
        main.lay.addLayout(row)
        self.body.addWidget(main)

        other = Card()
        other.lay.addWidget(label(tr("about.other"), "H2"))
        other.lay.addWidget(label("RIVOXO Games", "H2"))
        other.lay.addWidget(label(tr("about.rivoxo"), "Muted"))
        orow = QHBoxLayout()
        orow.addWidget(button("RIVOXO Games ↗", slot=lambda: open_url(links.rivoxo), tip=links.rivoxo))
        orow.addStretch(1)
        other.lay.addLayout(orow)
        self.body.addWidget(other)
        self.body.addWidget(label(tr("about.links_note") + f"\n{ctx.data_dir / 'config.json'}", "Muted"))
        self.finish()
