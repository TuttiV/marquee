/* Native test harness for decoders.h: test_decoders <inflate|lzma|zipentry> <compressed file> <expected size> <out file> */
#include <stdio.h>
#include "decoders.h"
int main(int argc, char **argv) {
    if (argc != 5) return 2;
    FILE *f = fopen(argv[2], "rb"); if (!f) return 3;
    fseek(f, 0, SEEK_END); long n = ftell(f); fseek(f, 0, SEEK_SET);
    uint8_t *in = malloc(n ? n : 1); if (fread(in, 1, n, f) != (size_t)n) return 3; fclose(f);
    size_t outLen = (size_t)strtoull(argv[3], NULL, 10);
    uint8_t *out = malloc(outLen ? outLen : 1);
    int rc;
    crcInit();
    if (!strcmp(argv[1], "inflate")) rc = inflateRaw(in, n, out, outLen);
    else if (!strcmp(argv[1], "zipentry")) rc = lzmaDecodeZipEntry(in, n, out, outLen);
    else return 2;
    if (rc != 0) { printf("decode failed: %d\n", rc); return 1; }
    FILE *o = fopen(argv[4], "wb"); fwrite(out, 1, outLen, o); fclose(o);
    printf("ok crc=%08x\n", crc32of(out, outLen) ), (void)0;
    return 0;
}
