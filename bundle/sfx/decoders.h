/* Decompression used by the self-extracting stub (and unit-tested natively by tests/test_sfx_decoders.py):
 * inflate (zip "deflate"), LZMA (zip method 14) and crc32. Plain C, no dependencies. */
#ifndef MARQUEE_DECODERS_H
#define MARQUEE_DECODERS_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>

/* ------------------------------------------------------------------ inflate (RFC 1951), after zlib's puff.c ---- */
typedef struct { const uint8_t *in; size_t inLen, inPos; uint32_t bitBuf; int bitCnt; uint8_t *out; size_t outLen, outPos; } Inflate;
typedef struct { short count[16]; short symbol[288]; } Huffman;

static int getBits(Inflate *s, int need) {
    long val = (long)s->bitBuf;
    while (s->bitCnt < need) {
        if (s->inPos >= s->inLen) return -1;
        val |= (long)s->in[s->inPos++] << s->bitCnt;
        s->bitCnt += 8;
    }
    s->bitBuf = (uint32_t)(val >> need);
    s->bitCnt -= need;
    return (int)(val & ((1L << need) - 1));
}

static int decodeSym(Inflate *s, const Huffman *h) {
    int code = 0, first = 0, index = 0;
    for (int len = 1; len <= 15; len++) {
        int bit = getBits(s, 1);
        if (bit < 0) return -1;
        code |= bit;
        int count = h->count[len];
        if (code - count < first) return h->symbol[index + (code - first)];
        index += count; first += count; first <<= 1; code <<= 1;
    }
    return -1;
}

static int construct(Huffman *h, const short *length, int n) {
    short offs[16];
    for (int len = 0; len <= 15; len++) h->count[len] = 0;
    for (int sym = 0; sym < n; sym++) h->count[length[sym]]++;
    if (h->count[0] == n) return 0;
    int left = 1;
    for (int len = 1; len <= 15; len++) { left <<= 1; left -= h->count[len]; if (left < 0) return left; }
    offs[1] = 0;
    for (int len = 1; len < 15; len++) offs[len + 1] = offs[len] + h->count[len];
    for (int sym = 0; sym < n; sym++) if (length[sym] != 0) h->symbol[offs[length[sym]]++] = (short)sym;
    return left;
}

static const short LBASE[29] = {3,4,5,6,7,8,9,10,11,13,15,17,19,23,27,31,35,43,51,59,67,83,99,115,131,163,195,227,258};
static const short LEXT[29] = {0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,3,3,3,3,4,4,4,4,5,5,5,5,0};
static const short DBASE[30] = {1,2,3,4,5,7,9,13,17,25,33,49,65,97,129,193,257,385,513,769,1025,1537,2049,3073,4097,6145,8193,12289,16385,24577};
static const short DEXT[30] = {0,0,0,0,1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8,9,9,10,10,11,11,12,12,13,13};

static int codes(Inflate *s, const Huffman *lencode, const Huffman *distcode) {
    for (;;) {
        int sym = decodeSym(s, lencode);
        if (sym < 0) return -1;
        if (sym < 256) {
            if (s->outPos >= s->outLen) return -1;
            s->out[s->outPos++] = (uint8_t)sym;
        } else if (sym == 256) {
            return 0;
        } else {
            sym -= 257;
            if (sym >= 29) return -1;
            int extra = getBits(s, LEXT[sym]);
            if (extra < 0) return -1;
            int len = LBASE[sym] + extra;
            sym = decodeSym(s, distcode);
            if (sym < 0 || sym >= 30) return -1;
            extra = getBits(s, DEXT[sym]);
            if (extra < 0) return -1;
            size_t dist = (size_t)DBASE[sym] + extra;
            if (dist > s->outPos || s->outPos + len > s->outLen) return -1;
            while (len--) { s->out[s->outPos] = s->out[s->outPos - dist]; s->outPos++; }
        }
    }
}

static int inflateRaw(const uint8_t *in, size_t inLen, uint8_t *out, size_t outLen) {
    static Huffman fixedLen, fixedDist;
    static int fixedReady = 0;
    Inflate s = { in, inLen, 0, 0, 0, out, outLen, 0 };
    int last;
    do {
        last = getBits(&s, 1);
        int type = getBits(&s, 2);
        if (last < 0 || type < 0) return -1;
        if (type == 0) {
            s.bitBuf = 0; s.bitCnt = 0;
            if (s.inPos + 4 > s.inLen) return -1;
            unsigned len = s.in[s.inPos] | (s.in[s.inPos + 1] << 8);
            unsigned nlen = s.in[s.inPos + 2] | (s.in[s.inPos + 3] << 8);
            s.inPos += 4;
            if (len != (~nlen & 0xffff) || s.inPos + len > s.inLen || s.outPos + len > s.outLen) return -1;
            memcpy(s.out + s.outPos, s.in + s.inPos, len);
            s.inPos += len; s.outPos += len;
        } else if (type == 1) {
            if (!fixedReady) {
                short lengths[288];
                int sym;
                for (sym = 0; sym < 144; sym++) lengths[sym] = 8;
                for (; sym < 256; sym++) lengths[sym] = 9;
                for (; sym < 280; sym++) lengths[sym] = 7;
                for (; sym < 288; sym++) lengths[sym] = 8;
                construct(&fixedLen, lengths, 288);
                for (sym = 0; sym < 30; sym++) lengths[sym] = 5;
                construct(&fixedDist, lengths, 30);
                fixedReady = 1;
            }
            if (codes(&s, &fixedLen, &fixedDist) != 0) return -1;
        } else if (type == 2) {
            static const short ORDER[19] = {16,17,18,0,8,7,9,6,10,5,11,4,12,3,13,2,14,1,15};
            short lengths[320];
            Huffman lencode, distcode;
            int nlen = getBits(&s, 5), ndist = getBits(&s, 5), ncode = getBits(&s, 4);
            if (nlen < 0 || ndist < 0 || ncode < 0) return -1;
            nlen += 257; ndist += 1; ncode += 4;
            if (nlen > 286 || ndist > 30) return -1;
            int index;
            for (index = 0; index < ncode; index++) { int v = getBits(&s, 3); if (v < 0) return -1; lengths[ORDER[index]] = (short)v; }
            for (; index < 19; index++) lengths[ORDER[index]] = 0;
            if (construct(&lencode, lengths, 19) != 0) return -1;
            index = 0;
            while (index < nlen + ndist) {
                int sym = decodeSym(&s, &lencode);
                if (sym < 0) return -1;
                if (sym < 16) {
                    lengths[index++] = (short)sym;
                } else {
                    int len = 0, rep;
                    if (sym == 16) { if (index == 0) return -1; len = lengths[index - 1]; rep = getBits(&s, 2); if (rep < 0) return -1; rep += 3; }
                    else if (sym == 17) { rep = getBits(&s, 3); if (rep < 0) return -1; rep += 3; }
                    else { rep = getBits(&s, 7); if (rep < 0) return -1; rep += 11; }
                    if (index + rep > nlen + ndist) return -1;
                    while (rep--) lengths[index++] = (short)len;
                }
            }
            if (lengths[256] == 0) return -1;
            int err = construct(&lencode, lengths, nlen);
            if (err && (err < 0 || nlen != lencode.count[0] + lencode.count[1])) return -1;
            err = construct(&distcode, lengths + nlen, ndist);
            if (err && (err < 0 || ndist != distcode.count[0] + distcode.count[1])) return -1;
            if (codes(&s, &lencode, &distcode) != 0) return -1;
        } else {
            return -1;
        }
    } while (!last);
    return s.outPos == outLen ? 0 : -1;
}

/* ------------------------------------------------------------------------------------------------- crc32 ---- */
static uint32_t crcTable[256];
static void crcInit(void) {
    for (uint32_t n = 0; n < 256; n++) {
        uint32_t c = n;
        for (int k = 0; k < 8; k++) c = (c & 1) ? 0xEDB88320u ^ (c >> 1) : c >> 1;
        crcTable[n] = c;
    }
}
static void crcInit(void);
static uint32_t crc32of(const uint8_t *data, size_t len) {
    uint32_t c = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) c = crcTable[(c ^ data[i]) & 0xFF] ^ (c >> 8);
    return c ^ 0xFFFFFFFFu;
}


/* ------------------------------------------------------------------------------ LZMA (raw stream, LZMA SDK spec) ---- */
typedef uint16_t LzmaProb;
typedef struct { const uint8_t *in, *end; uint32_t range, code; int err; } LzmaRC;

static uint8_t lzmaNext(LzmaRC *r) {
    if (r->in >= r->end) { r->err = 1; return 0; }
    return *r->in++;
}
static void lzmaNormalize(LzmaRC *r) {
    if (r->range < (1u << 24)) { r->range <<= 8; r->code = (r->code << 8) | lzmaNext(r); }
}
static uint32_t lzmaBit(LzmaRC *r, LzmaProb *p) {
    uint32_t v = *p, bound = (r->range >> 11) * v, symbol;
    if (r->code < bound) { v += (2048 - v) >> 5; r->range = bound; symbol = 0; }
    else { v -= v >> 5; r->code -= bound; r->range -= bound; symbol = 1; }
    *p = (LzmaProb)v;
    lzmaNormalize(r);
    return symbol;
}
static uint32_t lzmaDirect(LzmaRC *r, int bits) {
    uint32_t result = 0;
    while (bits--) {
        r->range >>= 1;
        r->code -= r->range;
        uint32_t t = 0 - (r->code >> 31);
        r->code += r->range & t;
        if (r->code == r->range) r->err = 1;
        lzmaNormalize(r);
        result = (result << 1) + t + 1;
    }
    return result;
}
static uint32_t lzmaTree(LzmaRC *r, LzmaProb *probs, int bits) {
    uint32_t m = 1;
    for (int i = 0; i < bits; i++) m = (m << 1) + lzmaBit(r, probs + m);
    return m - (1u << bits);
}
static uint32_t lzmaTreeReverse(LzmaRC *r, LzmaProb *probs, int bits) {
    uint32_t m = 1, symbol = 0;
    for (int i = 0; i < bits; i++) { uint32_t bit = lzmaBit(r, probs + m); m = (m << 1) + bit; symbol |= bit << i; }
    return symbol;
}
typedef struct { LzmaProb choice, choice2, low[16][8], mid[16][8], high[256]; } LzmaLen;
static uint32_t lzmaLength(LzmaRC *r, LzmaLen *l, uint32_t posState) {
    if (!lzmaBit(r, &l->choice)) return lzmaTree(r, l->low[posState], 3);
    if (!lzmaBit(r, &l->choice2)) return 8 + lzmaTree(r, l->mid[posState], 3);
    return 16 + lzmaTree(r, l->high, 8);
}

/* Decode a raw LZMA1 stream (props: the 5-byte lc/lp/pb + dictionary-size header) into out[0..outLen). 0 on success. */
static int lzmaDecode(const uint8_t *props, const uint8_t *in, size_t inLen, uint8_t *out, size_t outLen) {
    unsigned d = props[0];
    if (d >= 9 * 5 * 5) return -1;
    unsigned lc = d % 9; d /= 9;
    unsigned lp = d % 5, pb = d / 5;
    uint32_t dictSize = props[1] | (props[2] << 8) | (props[3] << 16) | ((uint32_t)props[4] << 24);
    (void)dictSize;
    if (inLen < 5 || in[0] != 0) return -1;

    size_t literalCount = (size_t)0x300 << (lc + lp);
    LzmaProb *literal = (LzmaProb *)malloc(literalCount * sizeof(LzmaProb));
    LzmaProb *posSlot = (LzmaProb *)malloc(4 * 64 * sizeof(LzmaProb));
    LzmaProb *posDecoders = (LzmaProb *)malloc(115 * sizeof(LzmaProb));
    LzmaProb *misc = (LzmaProb *)malloc((12 * 16 * 2 + 12 * 4 + 16) * sizeof(LzmaProb));
    LzmaLen *lengths = (LzmaLen *)malloc(2 * sizeof(LzmaLen));
    if (!literal || !posSlot || !posDecoders || !misc || !lengths) { free(literal); free(posSlot); free(posDecoders); free(misc); free(lengths); return -2; }
    LzmaProb *isMatch = misc, *isRep0Long = misc + 12 * 16, *isRep = misc + 12 * 16 * 2, *isRepG0 = isRep + 12,
             *isRepG1 = isRepG0 + 12, *isRepG2 = isRepG1 + 12, *align = isRepG2 + 12;
    for (size_t i = 0; i < literalCount; i++) literal[i] = 1024;
    for (int i = 0; i < 4 * 64; i++) posSlot[i] = 1024;
    for (int i = 0; i < 115; i++) posDecoders[i] = 1024;
    for (int i = 0; i < 12 * 16 * 2 + 12 * 4 + 16; i++) misc[i] = 1024;
    for (int k = 0; k < 2; k++) {
        LzmaLen *l = &lengths[k];
        l->choice = l->choice2 = 1024;
        for (int i = 0; i < 16; i++) for (int j = 0; j < 8; j++) l->low[i][j] = l->mid[i][j] = 1024;
        for (int i = 0; i < 256; i++) l->high[i] = 1024;
    }

    LzmaRC rc = { in + 5, in + inLen, 0xFFFFFFFFu, 0, 0 };
    rc.code = ((uint32_t)in[1] << 24) | ((uint32_t)in[2] << 16) | ((uint32_t)in[3] << 8) | in[4];
    unsigned state = 0;
    uint32_t rep0 = 0, rep1 = 0, rep2 = 0, rep3 = 0;
    size_t pos = 0;
    int result = 0;
    while (pos < outLen && !rc.err) {
        uint32_t posState = (uint32_t)pos & ((1u << pb) - 1);
        if (!lzmaBit(&rc, &isMatch[(state << 4) + posState])) {  /* Literal */
            uint32_t prev = pos ? out[pos - 1] : 0;
            LzmaProb *probs = literal + 0x300 * ((((uint32_t)pos & ((1u << lp) - 1)) << lc) + (prev >> (8 - lc)));
            uint32_t symbol = 1;
            if (state >= 7) {
                if (rep0 >= pos) { result = -1; break; }
                uint32_t matchByte = out[pos - rep0 - 1];
                do {
                    uint32_t matchBit = (matchByte >> 7) & 1;
                    matchByte <<= 1;
                    uint32_t bit = lzmaBit(&rc, probs + ((1 + matchBit) << 8) + symbol);
                    symbol = (symbol << 1) | bit;
                    if (matchBit != bit) break;
                } while (symbol < 0x100);
            }
            while (symbol < 0x100) symbol = (symbol << 1) | lzmaBit(&rc, probs + symbol);
            out[pos++] = (uint8_t)symbol;
            state = state < 4 ? 0 : (state < 10 ? state - 3 : state - 6);
            continue;
        }
        uint32_t len;
        if (lzmaBit(&rc, &isRep[state])) {
            if (pos == 0) { result = -1; break; }
            if (!lzmaBit(&rc, &isRepG0[state])) {
                if (!lzmaBit(&rc, &isRep0Long[(state << 4) + posState])) {  /* Short rep: one byte */
                    if (rep0 >= pos) { result = -1; break; }
                    state = state < 7 ? 9 : 11;
                    out[pos] = out[pos - rep0 - 1];
                    pos++;
                    continue;
                }
            } else {
                uint32_t dist;
                if (!lzmaBit(&rc, &isRepG1[state])) dist = rep1;
                else {
                    if (!lzmaBit(&rc, &isRepG2[state])) dist = rep2;
                    else { dist = rep3; rep3 = rep2; }
                    rep2 = rep1;
                }
                rep1 = rep0;
                rep0 = dist;
            }
            len = lzmaLength(&rc, &lengths[1], posState);
            state = state < 7 ? 8 : 11;
        } else {
            rep3 = rep2; rep2 = rep1; rep1 = rep0;
            len = lzmaLength(&rc, &lengths[0], posState);
            state = state < 7 ? 7 : 10;
            uint32_t lenState = len < 4 ? len : 3;
            uint32_t slot = lzmaTree(&rc, posSlot + lenState * 64, 6);
            if (slot < 4) rep0 = slot;
            else {
                uint32_t direct = (slot >> 1) - 1;
                uint32_t dist = (2 | (slot & 1)) << direct;
                if (slot < 14) dist += lzmaTreeReverse(&rc, posDecoders + dist - slot, (int)direct);
                else { dist += lzmaDirect(&rc, (int)direct - 4) << 4; dist += lzmaTreeReverse(&rc, align, 4); }
                rep0 = dist;
            }
            if (rep0 == 0xFFFFFFFFu) break;  /* End marker */
        }
        len += 2;
        if (rep0 >= pos) { result = -1; break; }
        if (pos + len > outLen) len = (uint32_t)(outLen - pos);
        while (len--) { out[pos] = out[pos - rep0 - 1]; pos++; }
    }
    free(literal); free(posSlot); free(posDecoders); free(misc); free(lengths);
    if (result != 0 || rc.err) return -1;
    return pos == outLen ? 0 : -1;
}

/* Zip method 14: 2 bytes version, 2 bytes props size (5), the props, then the raw LZMA stream. */
static int lzmaDecodeZipEntry(const uint8_t *data, size_t size, uint8_t *out, size_t outLen) {
    if (size < 9 || (data[2] | (data[3] << 8)) != 5) return -1;
    return lzmaDecode(data + 4, data + 9, size - 9, out, outLen);
}

#endif
