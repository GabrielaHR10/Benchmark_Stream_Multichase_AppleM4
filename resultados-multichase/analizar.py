#!/usr/bin/env python3
"""
Procesamiento de los CSV de multichase (Seccion 6 del esquema de pruebas).
Calcula estadisticos y emite los bloques de coordenadas para pgfplots.
No inventa datos: todo sale de los CSV.
"""
import csv
import os
import statistics as st

BASE = os.path.dirname(os.path.abspath(__file__))


def leer(nombre):
    with open(os.path.join(BASE, nombre), newline="") as fh:
        return [{k: v.strip() for k, v in r.items()} for r in csv.DictReader(fh)]


def humano(b):
    b = float(b)
    for u, f in (("GiB", 2**30), ("MiB", 2**20), ("KiB", 2**10)):
        if b >= f:
            return f"{b/f:g} {u}"
    return f"{b:g} B"


out = []
W = out.append

# ------------------------------------------------------------------ Prueba 1
p1 = leer("p1_tamano.csv")
b1 = [int(r["size_bytes"]) for r in p1]
l1 = [float(r["latencia_ns"]) for r in p1]
e1 = [r["size_label"] for r in p1]

W("=== P1 coords (pgfplots) ===")
W(" ".join(f"({b},{l})" for b, l in zip(b1, l1)))

W("\n=== P1 saltos relativos entre puntos consecutivos ===")
saltos = []
for i in range(1, len(l1)):
    pct = (l1[i] - l1[i - 1]) / l1[i - 1] * 100
    saltos.append((pct, e1[i - 1], e1[i], l1[i - 1], l1[i]))
for pct, a, b, la, lb in saltos:
    marca = "  <== CODO" if pct >= 15 else ""
    W(f"  {a:>5} -> {b:<5} {la:7.3f} -> {lb:7.3f} ns  ({pct:+7.1f} %){marca}")

W("\n=== P1 saltos ordenados por magnitud ===")
for pct, a, b, la, lb in sorted(saltos, reverse=True)[:8]:
    W(f"  {a:>5} -> {b:<5} {la:7.3f} -> {lb:7.3f} ns  ({pct:+7.1f} %)")

W("\n=== P1 mesetas (promedio por region) ===")


def meseta(lo, hi):
    v = [l for e, l in zip(e1, l1) if lo <= e1.index(e) <= hi]
    return v


regiones = [("4k..128k", 0, 6), ("160k..6m", 7, 17), ("8m..32m", 18, 27),
            ("96m..1g", 31, 38)]
for nom, i, j in regiones:
    v = l1[i:j + 1]
    W(f"  {nom:<10} n={len(v):2d}  media {st.mean(v):7.3f} ns  "
      f"min {min(v):7.3f}  max {max(v):7.3f}")

W("\n=== P1 tabla completa ===")
for b, e, l in zip(b1, e1, l1):
    W(f"  {e:>5} {humano(b):>9} {l:8.3f}")

# ------------------------------------------------------------------ Prueba 2
p2 = leer("p2_stride.csv")
ser = {}
for r in p2:
    ser.setdefault(r["tamano"], []).append(
        (int(r["stride_bytes"]), float(r["latencia_ns"])))
for k in ser:
    ser[k].sort()
    W(f"\n=== P2 coords {k} ===")
    W(" ".join(f"({s},{l})" for s, l in ser[k]))
    base = dict(ser[k])[128]
    W(f"  referencia s=128: {base} ns")
    for s, l in ser[k]:
        W(f"    s={s:<6} {l:8.3f} ns   ratio vs 128B = {l/base:5.2f}x")

# ------------------------------------------------------------------ Prueba 3
p3 = leer("p3_hilos.csv")
h3 = [int(r["hilos"]) for r in p3]
l3 = [float(r["latencia_ns"]) for r in p3]
W("\n=== P3 coords ===")
W(" ".join(f"({h},{l})" for h, l in zip(h3, l3)))
base3 = l3[0]
for h, l in zip(h3, l3):
    W(f"  t={h:<3} {l:8.3f} ns   x{l/base3:5.2f} vs 1 hilo")
W("  saltos consecutivos:")
for i in range(1, len(l3)):
    W(f"    {h3[i-1]:>2} -> {h3[i]:<2}  {(l3[i]-l3[i-1])/l3[i-1]*100:+7.1f} %")

# ------------------------------------------------------------------ Prueba 4
p4 = leer("p4_repetibilidad.csv")
g = {}
for r in p4:
    g.setdefault(r["tamano"], []).append(float(r["latencia_ns"]))
W("\n=== P4 estadisticos ===")
for k in ("64k", "8m", "20m", "256m"):
    v = g[k]
    m, s = st.mean(v), st.stdev(v)
    W(f"  {k:>5}  n={len(v)}  media {m:8.4f}  desv {s:7.4f}  "
      f"({s/m*100:5.2f} %)  min {min(v):7.3f}  max {max(v):7.3f}  "
      f"rango {max(v)-min(v):6.3f}")
    W(f"         valores: {v}")

texto = "\n".join(out)
print(texto)
with open(os.path.join(BASE, "metricas.txt"), "w") as fh:
    fh.write(texto + "\n")
