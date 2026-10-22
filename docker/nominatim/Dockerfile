# mediagis/nominatim:4.4 con el PHP de Ubuntu actualizado (php2shell,
# CVE-2026-109618/109619, corregido en php8.1 8.1.2-1ubuntu2.28, USN-8948).
FROM mediagis/nominatim:4.4

RUN apt-get update \
    && apt-get install -y --only-upgrade $(dpkg-query -W -f '${db:Status-Abbrev} ${Package}\n' 'php8.1*' 'libapache2-mod-php8.1' | awk '$1=="ii" {print $2}') \
    && rm -rf /var/lib/apt/lists/*

# Capa extra: cierra la vía de upload progress aunque se vuelva a una imagen sin parche.
COPY php-hardening.ini /etc/php/8.1/apache2/conf.d/99-php2shell.ini
