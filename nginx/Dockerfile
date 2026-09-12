# syntax=docker/dockerfile:1

# The config is baked in rather than bind-mounted.
#
# A single-file bind mount binds an inode, not a path. Git replaces a file on
# checkout rather than rewriting it, so after a deploy the container went on
# serving the old inode -- a config change could be committed, deployed and
# still not be running, with nothing to show for it. Baking it in means any
# change produces a different image, and compose recreates the container.
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf

RUN nginx -t
