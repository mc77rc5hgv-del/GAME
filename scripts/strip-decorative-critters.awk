# Removes ambient sea-creature and decorative elements (fish schools,
# crabs, snails, sea urchins, animated seaweed/anemones) from a single
# Jumpy level file. Run once per file:
#   awk -f scripts/strip-decorative-critters.awk level.map.yaml > tmp && mv tmp level.map.yaml
#
# Pure awk (no python3 dependency - Windows Git Bash users often only have
# a non-functional python3 App Execution Alias stub, which silently broke
# this step when it was a Python script). See fetch-dev-assets.sh.
BEGIN {
    n_strip = split( \
        "/elements/environment/fish_school/fish_school.element.yaml " \
        "/elements/environment/crab/crab.element.yaml " \
        "/elements/environment/snail/snail.element.yaml " \
        "/elements/environment/urchin/urchin.element.yaml " \
        "/elements/decoration/seaweed/seaweed.element.yaml " \
        "/elements/decoration/anemones/anemones.element.yaml", \
        strip_arr, " ")
    for (k = 1; k <= n_strip; k++) strip[strip_arr[k]] = 1
}
{
    # Normalize CRLF to LF first - at least one shipped level file uses
    # Windows line endings, which broke the pattern matches below (\r was
    # sneaking past the "$" anchors).
    line = $0
    sub(/\r$/, "", line)
    lines[NR] = line
}
END {
    n = NR
    i = 1
    out_n = 0
    while (i <= n) {
        line = lines[i]

        if (line ~ /^- id: critters[ \t]*$/) {
            i++
            while (i <= n && lines[i] !~ /^- id: /) i++
            continue
        }

        if (line ~ /^  - pos:[ \t]*$/ && (i + 3) <= n && lines[i+3] ~ /^    element: /) {
            elem = lines[i+3]
            sub(/^    element: /, "", elem)
            gsub(/[ \t]+$/, "", elem)
            if (elem in strip) {
                i += 4
                continue
            }
        }

        if (line ~ /^  - \{.*element:/) {
            elem = line
            sub(/.*element:[ \t]*/, "", elem)
            sub(/[ \t]*\}[ \t]*$/, "", elem)
            if (elem in strip) {
                i++
                continue
            }
        }

        out_n++
        out[out_n] = line
        i++
    }
    for (j = 1; j <= out_n; j++) print out[j]
}
