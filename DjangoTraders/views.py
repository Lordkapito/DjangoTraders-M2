"""
Project-level views for DjangoTraders.

Unlike djtraders/views.py, this file isn't inside a Django *app* --
it's a small views.py living alongside the project's settings.py and
urls.py. That's a deliberate choice for a single "site home page" that
isn't really part of any one app's feature set; it's the entry point
to the whole project. If more project-wide pages are needed later,
this is where they'd go too.

  1. home now doubles as a manual, simulated "session clear."
        There's no reliable way for the app to detect a browser actually
        closing (see this project's own Module 2 changelog entry, "A
        session outlives the server process") -- so instead of trying,
        visiting this page while an employee or customer is logged in
        shows an in-page confirmation (a Bootstrap alert, home.html)
        asking to start a new session; only a real POST -- its own Yes
        button -- actually clears both session keys. A plain GET with
        nobody logged in still renders the normal page, unchanged.
"""
from django.shortcuts import redirect, render


def home(request):
    """
    Project home page.

    Links into the djtraders app's own home page. As more apps join
    the project, this page becomes the index that lists all of them.

    Also this project's "start a new session" action (see this file's
    own changelog entry 1). POST here -- home.html's own confirmation
    alert, submitted via its Yes button -- pops current_user and
    customer_id from the session and redirects back to this same page,
    which then renders normally (nobody logged in). A GET while either
    session key is still set shows that confirmation instead of the
    normal page content; a GET with neither set renders normally too --
    that covers both an anonymous visitor and the redirect right after
    the POST above.
    """
    if request.method == "POST":
        request.session.pop("current_user", None)
        request.session.pop("customer_id", None)
        return redirect("home")

    confirm_logout = bool(
        request.session.get("current_user") or request.session.get("customer_id")
    )

    # "home.html" (no "djtraders/" prefix) is found via TEMPLATES['DIRS']
    # in settings.py, not via an app's own templates/ folder.
    return render(request, "home.html", {"confirm_logout": confirm_logout})
