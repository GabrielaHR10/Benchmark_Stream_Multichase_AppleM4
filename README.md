# Taller de Jerarquía de Memoria: STREAM + multichase

Taller de HPC sobre la caracterización de la jerarquía de memoria de un sistema Apple Silicon
(10 núcleos, ARM64). Se combinan dos herramientas complementarias:

- **STREAM** (John D. McCalpin) → mide **ancho de banda** sostenido de memoria (MB/s).
- **multichase** → mide **latencia** de acceso mediante *pointer chasing* (ns por acceso).

Con STREAM se observa cuánto dato por segundo puede mover el sistema en cada nivel de la
jerarquía; con multichase se detectan los "codos" que delatan los tamaños de caché y la
latencia de la RAM.

El análisis completo está en [`informe_Stream_Multichase.pdf`](informe_Stream_Multichase.pdf) (20 páginas).

---

## Estructura del repositorio

```
.
├── informe_Stream_Multichase.pdf   Informe final del taller
├── Stream/
│   ├── stream.c                    Fuente original de STREAM v5.10
│   ├── resultados_stream_cache.log Corridas por nivel de jerarquía (l1, l2, slc, ram)
│   └── resultados_stream_threads.log Escalamiento con 1,2,3,4,6,8,10 hilos OpenMP
└── resultados-multichase/
    ├── p1_tamano.csv               P1: latencia vs. tamaño del working set (4 KiB → 1 GiB)
    ├── p2_stride.csv               P2: latencia vs. stride (16 B → 16 KiB) en 8m y 256m
    ├── p3_hilos.csv                P3: latencia vs. número de hilos (1 → 10)
    ├── p4_repetibilidad.csv        P4: 5 repeticiones en 64k, 8m, 20m y 256m
    ├── analizar.py                 Procesa los CSV y genera métricas + coords pgfplots
    ├── metricas.txt                Salida de analizar.py (usada en el informe)
    └── entorno_contenedor.txt      lscpu, meminfo, gcc y commit del contenedor
```

Los binarios de STREAM (`stream_l1`, `stream_l2`, `stream_slc`, `stream_ram`, …) **no se versionan**:
son artefactos de compilación y se regeneran con los comandos de más abajo.

---

## Entorno de medición

| | STREAM | multichase |
|---|---|---|
| Plataforma | macOS nativo (arm64) | Contenedor Ubuntu 24.04 (aarch64) |
| CPU | Apple Silicon, 10 núcleos | Apple Silicon, 10 núcleos (vía contenedor) |
| Memoria | — | 8 025 424 kB (`MemTotal`) |
| Compilador | clang + `libomp` (Homebrew) | gcc 13.3.0 |
| Versión | STREAM v5.10 | multichase commit `8cc8681` |

El detalle exacto del contenedor está en [`resultados-multichase/entorno_contenedor.txt`](resultados-multichase/entorno_contenedor.txt).

---

## Reproducir las mediciones

### STREAM

`stream.c` se compila una vez por nivel de la jerarquía, variando `STREAM_ARRAY_SIZE` para que
los tres arreglos (`a`, `b`, `c`, de 8 B por elemento) quepan —o no— en el nivel objetivo:

```bash
cd Stream

# L1  →   2 500 elem  (~0.06 MiB totales)
clang -O2 -fopenmp -DSTREAM_ARRAY_SIZE=2500     -DNTIMES=50 stream.c -o stream_l1  -lomp
# L2  → 350 000 elem  (~8 MiB totales)
clang -O2 -fopenmp -DSTREAM_ARRAY_SIZE=350000   -DNTIMES=50 stream.c -o stream_l2  -lomp
# SLC → 900 000 elem  (~20.6 MiB totales)
clang -O2 -fopenmp -DSTREAM_ARRAY_SIZE=900000   -DNTIMES=50 stream.c -o stream_slc -lomp
# RAM →  40 000 000 elem (~915 MiB totales)
clang -O2 -fopenmp -DSTREAM_ARRAY_SIZE=40000000 -DNTIMES=20 stream.c -o stream_ram -lomp
```

> En macOS, Apple clang necesita `libomp` de Homebrew (`brew install libomp`) y las rutas
> `-I$(brew --prefix libomp)/include -L$(brew --prefix libomp)/lib`. Con gcc basta `-fopenmp`.

Corridas:

```bash
# Barrido por nivel de jerarquía (1 hilo) → resultados_stream_cache.log
for n in l1 l2 slc ram; do
  echo "=== $n ==="; OMP_NUM_THREADS=1 ./stream_$n
done > resultados_stream_cache.log

# Escalamiento de hilos sobre el tamaño de RAM → resultados_stream_threads.log
for t in 1 2 3 4 6 8 10; do
  echo "=== hilos=$t ==="; OMP_NUM_THREADS=$t ./stream_ram
done > resultados_stream_threads.log
```

### multichase

```bash
git clone https://github.com/google/multichase
cd multichase && git checkout 8cc8681 && make

./multichase -m <tamaño>            # P1: barrido de tamaño
./multichase -m 8m -s <stride>      # P2: barrido de stride
./multichase -m 256m -t <hilos>     # P3: barrido de hilos
```

Las latencias reportadas se vuelcan a los CSV de `resultados-multichase/`.

### Análisis

```bash
cd resultados-multichase
python3 analizar.py     # imprime y reescribe metricas.txt
```

`analizar.py` no requiere dependencias externas (solo `csv` y `statistics`): calcula saltos
relativos, mesetas por región, ratios de stride, escalamiento por hilos y desviación estándar,
y emite las coordenadas listas para `pgfplots`.

---

## Resultados principales

### Ancho de banda (STREAM, 1 hilo)

| Nivel | Arreglo (elem) | Copy | Scale | Add | Triad |
|---|---:|---:|---:|---:|---:|
| L1 | 2 500 | (inf)¹ | (inf)¹ | 62 914.6 | 62 914.6 |
| L2 | 350 000 | 109 757.5 | 79 891.5 | 80 073.1 | 79 173.4 |
| SLC | 900 000 | 156 471.4 | 116 150.0 | 120 635.1 | 117 353.6 |
| RAM | 40 000 000 | 88 020.3 | 85 491.7 | 93 714.4 | 93 740.6 |

Valores en MB/s (*best rate*). ¹ El caso L1 queda por debajo de la resolución del reloj
(≈8 µs por kernel, granularidad de 1 µs), por lo que Copy y Scale reportan `inf`: ese punto
no es una medición válida, solo confirma que el arreglo cabe holgadamente en L1.

### Escalamiento de hilos (STREAM, arreglo de ~915 MiB)

| Hilos | 1 | 2 | 3 | 4 | 6 | 8 | 10 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Triad (MB/s) | 93 777.7 | 96 229.5 | 97 193.5 | 97 186.5 | 97 591.6 | 97 402.7 | 97 452.2 |

El ancho de banda satura prácticamente con 2–3 hilos: el cuello de botella es el bus de
memoria, no el cómputo.

### Latencia vs. tamaño (multichase, P1)

Mesetas promedio detectadas:

| Región | n | Media | Mín | Máx |
|---|---:|---:|---:|---:|
| 4 KiB – 128 KiB | 7 | 1.455 ns | 1.451 | 1.464 |
| 160 KiB – 6 MiB | 11 | 10.087 ns | 7.633 | 11.454 |
| 8 MiB – 32 MiB | 10 | 13.773 ns | 11.114 | 17.532 |
| 96 MiB – 1 GiB | 8 | 41.324 ns | 39.250 | 48.358 |

Codos más marcados (saltos ≥ 15 % entre puntos consecutivos):

| Transición | Salto |
|---|---:|
| 128 KiB → 160 KiB | **+421.4 %** (1.464 → 7.633 ns) — salida de L1 |
| 32 MiB → 40 MiB | +63.3 % (17.532 → 28.634 ns) |
| 64 MiB → 96 MiB | +52.2 % (25.962 → 39.527 ns) — entrada plena a RAM |
| 48 MiB → 64 MiB | +25.2 % |
| 16 MiB → 18 MiB | +23.4 % |

### Latencia vs. stride (multichase, P2)

Con un working set de 8 MiB la latencia apenas se mueve (7.5 → 14.5 ns): el conjunto sigue en
caché y el prefetcher absorbe el patrón. Con 256 MiB el efecto es dramático — de 10.7 ns
(stride 16 B) a 105.4 ns (stride 1 KiB), un **2.61×** sobre la referencia de 128 B — porque cada
salto desperdicia la línea de caché y termina fallando también en TLB. A partir de 2 KiB la
latencia vuelve a bajar (66.8 ns en 4 KiB, 48.9 ns en 16 KiB) al reducirse el número de páginas
distintas tocadas.

### Latencia vs. hilos (multichase, P3, 256 MiB)

| Hilos | 1 | 2 | 3 | 4 | 5 | 6 | 8 | 10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Latencia (ns) | 39.3 | 38.7 | 38.0 | 80.8 | 88.8 | 90.6 | 122.7 | 128.1 |

Hasta 3 hilos la latencia se mantiene plana; en el 4.º salta **+112.8 %**, coherente con el paso
del clúster de núcleos de rendimiento a los de eficiencia y con la contención del bus.

### Repetibilidad (multichase, P4, 5 corridas)

| Tamaño | Media | Desv. est. | CV |
|---|---:|---:|---:|
| 64 KiB | 1.4480 ns | 0.0067 | 0.47 % |
| 8 MiB | 10.5408 ns | 0.1530 | 1.45 % |
| 20 MiB | 12.3824 ns | 0.2253 | 1.82 % |
| 256 MiB | 39.1418 ns | 0.1375 | 0.35 % |

Coeficientes de variación por debajo del 2 % en todos los casos: las mediciones son estables.

---

## Créditos y licencias

- **STREAM** — © 1991-2013 John D. McCalpin, University of Virginia.
  <https://www.cs.virginia.edu/stream/>. `Stream/stream.c` se incluye sin modificaciones;
  los resultados publicados aquí siguen las *STREAM Run Rules* y las condiciones de uso
  declaradas en la cabecera del propio archivo.
- **multichase** — Google, <https://github.com/google/multichase> (licencia Apache 2.0).
- Mediciones, scripts de análisis e informe: trabajo del taller.
