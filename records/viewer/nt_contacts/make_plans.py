"""Write the pre-registered browser plans (PREREG_NT_CONTACTS.md, part B) for the three demonstration pages.
usage: python make_plans.py KIND PAGE_DIR PROJECT_DIR ANALYSIS_DIR OUT_PLAN_JSON   (KIND: 2JEA | 1VTM | 6BJG_t0.5)
Structure order comes from the page's viewer_manifest.json; ids, chains and designation from the project manifest;
the reverse-click protein residue from Report's record. Nothing about expected highlights is written here (the checker
derives them from Report's record)."""
import json
import os
import sys


def main(kind, page, project, analysis, out):
    vm = json.load(open(os.path.join(page, "viewer_manifest.json")))
    man = json.load(open(os.path.join(project, "manifest.json")))
    cbo = json.load(open(os.path.join(analysis, "report", "contacts_by_output.json")))
    by_used = {os.path.realpath(s["used_path"]): s for s in man["structures"] if s.get("used_path")}
    order = [by_used[os.path.realpath(s["source"])] for s in vm["structures"]]
    ids = [s["id"] for s in order]
    rna_chain = [c["chain"] for c in order[0]["chains"] if c.get("type_by_report") == "rna"][0]
    prot_chain = [c["chain"] for c in order[0]["chains"] if c.get("type_by_report") == "protein"][0]
    L = len(man["construct"]["rna_sequence"])
    steps, rng = [], None

    def add(i, do, shot=False, **kw):
        steps.append(dict(id="%02d_%s" % (len(steps), i), do=do, shot=shot, **kw))

    def click(i, pos, shot=False, mouse=True, chain=None):
        add(i, "click", shot, chain=chain or rna_chain, auth=pos, ins="", require_mouse=mouse)

    if kind == "2JEA":
        rng = [26, 35]
        des = [k for k, s in enumerate(order) if s.get("designated")]
        k0, k1 = des[0], des[1]                       # the two engine-designated structures (exec_A, exec_B model_0)
        assert k0 == 0, "the page opens on the first designated structure"
        add("overall", "load", True)
        click("B33", 33, True); click("B35", 35, True); click("B30", 30, True)
        add("clear", "clear", True)
        add("show_%s" % ids[k1], "show", True, k=k1)
        click("%s_B33" % ids[k1], 33, True); click("%s_B35" % ids[k1], 35); click("%s_B30" % ids[k1], 30)
        add("%s_clear" % ids[k1], "clear")
        click("%s_B33_again" % ids[k1], 33)
        add("prev_to_%s" % ids[k1 - 1], "prev", True)
        add("next_to_%s" % ids[k1], "next")
        add("mode_all", "mode", True, m="all")
        key = "%s|%s" % (order[k1]["engine"], order[k1]["execution"])
        p = min(p for p, r in cbo[key] if r == 33)
        click("reverse_%s%d" % (prot_chain, p), p, True, mouse=False, chain=prot_chain)
        add("mode_focus", "mode", m="focus")
        click("B26", 26, True); click("B26_toggle_off", 26)
        sweep = range(rng[0], rng[1] + 1)
    elif kind == "1VTM":
        rng = [1, 3]
        add("overall", "load", True)
        click("R1", 1, True); click("R2", 2); click("R3", 3, True)
        add("clear", "clear", True)
        add("next", "next", True); click("next_R2", 2, True)
        add("clear2", "clear")
        sweep = range(1, 4)
    elif kind == "6BJG_t0.5":
        add("overall", "load", True)
        click("R19", 19, True)
        for k in range(1, len(order)):
            add("next_%s" % ids[k], "next", True)
        click("last_R20", 20, True)
        add("mode_all", "mode", True, m="all")
        add("clear", "clear", True)
        add("mode_focus", "mode", m="focus")
        sweep = range(1, L + 1)
    else:
        raise SystemExit("unknown kind")
    for k in range(len(order)):                       # programmatic sweep: every structure x every position
        add("sweep_%s" % ids[k], "show", k=k)
        add("sweep_%s_clear" % ids[k], "clear")
        for pos in sweep:
            add("sweep_%s_%s%d" % (ids[k], rna_chain, pos), "api_select", molecule="rna", chain=rna_chain, pos=pos)
    add("final_clear", "clear")
    plan = {"tag": kind.replace(".", ""), "page": os.path.join(os.path.abspath(page), "viewer.html"), "kind": kind,
            "rna_range": rng, "structure_ids": ids, "rna_chain": rna_chain, "protein_chain": prot_chain, "steps": steps}
    with open(out, "w") as fh:
        json.dump(plan, fh, indent=1)
    print("%s: %d steps, %d structures" % (kind, len(steps), len(ids)))


if __name__ == "__main__":
    main(*sys.argv[1:6])
