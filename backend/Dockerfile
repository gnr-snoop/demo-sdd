FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps for psycopg/asyncpg, image handling, and opencv-python-headless
# (spec 008, FR-014). The headless variant excludes GUI/display modules but
# still needs libglib2.0-0 and libsm6 for the DNN + face modules.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libpq-dev git \
        libglib2.0-0 libsm6 \
        libxcb1 libxkbcommon0 libxkbcommon-x11-0 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN mkdir -p src/face_insight && touch src/face_insight/__init__.py
RUN pip install --upgrade pip "setuptools<80" wheel
# MiVOLO's setup.py uses pkg_resources (removed in setuptools 80+).
# Clone, patch setup.py to parse requirements without pkg_resources, then install.
RUN git clone --depth 1 https://github.com/WildChlamydia/MiVOLO.git /tmp/mivolo && \
    python -c "\
import re; \
p = open('/tmp/mivolo/setup.py').read(); \
p = re.sub(r'import pkg_resources as pkg\n', '', p); \
p = p.replace(\
    'REQUIREMENTS = [f\"{x.name}{x.specifier}\" for x in pkg.parse_requirements((PARENT / \"requirements.txt\").read_text())]',\
    'REQUIREMENTS = [l.strip() for l in (PARENT / \"requirements.txt\").read_text().splitlines() if l.strip() and not l.strip().startswith(\"#\")]'); \
open('/tmp/mivolo/setup.py', 'w').write(p)" && \
    pip install --no-build-isolation /tmp/mivolo && \
    rm -rf /tmp/mivolo
RUN pip install .

COPY . .
RUN pip install . --no-deps

# Spec 008 (FR-008/FR-010): models/ cache dir, bind-mounted from the host.
# Created here so the path exists even on a fresh image; the compose volume
# overlays it at runtime.
RUN mkdir -p /app/models

EXPOSE 8000

# Default command is overridden by docker-compose to run migrations first.
CMD ["uvicorn", "face_insight.main:app", "--host", "0.0.0.0", "--port", "8000"]
