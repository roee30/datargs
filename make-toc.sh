#!/bin/bash
markdown-toc -i README.md
sed -E -i 's/\* \[Use \[(.*?)\]\(.*\)\?\]/* [Use \1]/' README.md
