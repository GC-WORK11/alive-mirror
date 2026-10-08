// Alive — T1 fuzzy search index. Bit-identical semantics with
// server/alive_core_ref.py (see include/alive/search.hpp for the spec).

#include "alive/search.hpp"

#include <algorithm>
#include <cmath>
#include <cstring>
#include <unordered_set>
#include <utility>

#include "fold_table.inc"  // kFoldTable / kFoldTableSize (generated)

namespace alive {
namespace {

// ---------------------------------------------------------------------------
// ASCII fold: binary-search the generated NFKD->ascii table.
// ---------------------------------------------------------------------------
const char* fold_lookup(uint32_t cp) {
  unsigned lo = 0, hi = kFoldTableSize;
  while (lo < hi) {
    unsigned mid = (lo + hi) / 2;
    if (kFoldTable[mid].first < cp)
      lo = mid + 1;
    else
      hi = mid;
  }
  if (lo < kFoldTableSize && kFoldTable[lo].first == cp)
    return kFoldTable[lo].second;
  return nullptr;
}

inline bool is_alnum_ascii(char c) {
  return (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9');
}

// Padded trigram key: 3 bytes packed little-endian. Pad char is ' ' (0x20),
// which can never appear inside a normalized token.
inline uint32_t tri_key(char a, char b, char c) {
  return (uint32_t)(unsigned char)a | ((uint32_t)(unsigned char)b << 8) |
         ((uint32_t)(unsigned char)c << 16);
}

std::vector<uint32_t> trigrams(const std::string& tok) {
  std::vector<uint32_t> out;
  out.reserve(tok.size() + 2);
  std::string p = "  " + tok + "  ";
  for (size_t i = 0; i + 2 < p.size(); ++i)
    out.push_back(tri_key(p[i], p[i + 1], p[i + 2]));
  return out;
}

}  // namespace

// ---------------------------------------------------------------------------
// normalize — identical to alive_core_ref.normalize():
//   NFKD-fold each codepoint to ASCII (drop chars that fold to nothing WITHOUT
//   emitting a separator — Python's encode('ascii','ignore') semantics),
//   lowercase, keep [a-z0-9], everything else is a token separator.
// ---------------------------------------------------------------------------
std::vector<std::string> normalize(const std::string& s) {
  std::vector<std::string> out;
  std::string cur;

  auto flush = [&]() {
    if (!cur.empty()) {
      out.push_back(std::move(cur));
      cur.clear();
    }
  };
  auto emit = [&](char c) {
    if (c >= 'A' && c <= 'Z') c = (char)(c + ('a' - 'A'));
    if (is_alnum_ascii(c))
      cur.push_back(c);
    else
      flush();
  };

  size_t i = 0, n = s.size();
  while (i < n) {
    unsigned char c = (unsigned char)s[i];
    uint32_t cp;
    if (c < 0x80) {
      cp = c;
      i += 1;
    } else if ((c & 0xE0) == 0xC0 && i + 1 < n) {
      cp = ((uint32_t)(c & 0x1F) << 6) | ((unsigned char)s[i + 1] & 0x3F);
      i += 2;
    } else if ((c & 0xF0) == 0xE0 && i + 2 < n) {
      cp = ((uint32_t)(c & 0x0F) << 12) | (((unsigned char)s[i + 1] & 0x3F) << 6) |
           ((unsigned char)s[i + 2] & 0x3F);
      i += 3;
    } else if ((c & 0xF8) == 0xF0 && i + 3 < n) {
      cp = ((uint32_t)(c & 0x07) << 18) |
           (((unsigned char)s[i + 1] & 0x3F) << 12) |
           (((unsigned char)s[i + 2] & 0x3F) << 6) |
           ((unsigned char)s[i + 3] & 0x3F);
      i += 4;
    } else {
      cp = 0xFFFD;  // invalid byte — treated as a non-folding char (dropped)
      i += 1;
    }

    if (cp < 128) {
      emit((char)cp);
    } else if (const char* f = fold_lookup(cp)) {
      for (const char* p = f; *p; ++p) emit(*p);
    }
    // codepoints with no fold are dropped with NO separator, matching
    // Python's str.encode('ascii', 'ignore')
  }
  flush();
  return out;
}

// ---------------------------------------------------------------------------
// True Damerau-Levenshtein (optimal string alignment WITH adjacent
// transposition via the da[] last-occurrence map — the unrestricted metric).
// `bound` is used only to reject |len(a)-len(b)| > bound early; the full
// matrix is computed otherwise. Mirrors ref dl_distance() line for line.
// ---------------------------------------------------------------------------
int dl_distance(const std::string& a, const std::string& b, int bound) {
  const int la = (int)a.size(), lb = (int)b.size();
  if (std::abs(la - lb) > bound) return bound + 1;
  const int INF = la + lb;
  std::vector<int> d((size_t)(la + 2) * (lb + 2));
  auto D = [&](int i, int j) -> int& { return d[(size_t)i * (lb + 2) + j]; };
  D(0, 0) = INF;
  for (int i = 0; i <= la; ++i) {
    D(i + 1, 0) = INF;
    D(i + 1, 1) = i;
  }
  for (int j = 0; j <= lb; ++j) {
    D(0, j + 1) = INF;
    D(1, j + 1) = j;
  }
  int da[256] = {0};
  for (int i = 1; i <= la; ++i) {
    int db = 0;
    for (int j = 1; j <= lb; ++j) {
      int i1 = da[(unsigned char)b[j - 1]];
      int j1 = db;
      int cost = (a[i - 1] == b[j - 1]) ? 0 : 1;
      if (cost == 0) db = j;
      int v = D(i, j) + cost;
      v = std::min(v, D(i + 1, j) + 1);
      v = std::min(v, D(i, j + 1) + 1);
      v = std::min(v, D(i1, j1) + (i - i1 - 1) + 1 + (j - j1 - 1));
      D(i + 1, j + 1) = v;
    }
    da[(unsigned char)a[i - 1]] = i;
  }
  return D(la + 1, lb + 1);
}

double haversine_km(double lat1, double lon1, double lat2, double lon2) {
  const double kR = 6371.0088;
  const double kD2R = 0.017453292519943295;  // pi / 180
  double p1 = lat1 * kD2R, p2 = lat2 * kD2R;
  double dp = (lat2 - lat1) * kD2R, dl = (lon2 - lon1) * kD2R;
  double h = std::sin(dp / 2) * std::sin(dp / 2) +
             std::cos(p1) * std::cos(p2) * std::sin(dl / 2) * std::sin(dl / 2);
  return 2 * kR * std::asin(std::min(1.0, std::sqrt(h)));
}

// ---------------------------------------------------------------------------
// Build
// ---------------------------------------------------------------------------
SearchIndex::SearchIndex(std::vector<Entry> entries, AliasMap aliases,
                         Weights w)
    : entries_(std::move(entries)), aliases_(std::move(aliases)), w_(w) {
  std::unordered_map<std::string, std::vector<uint32_t>> postmap;
  std::unordered_set<std::string> toks;
  entry_toks_.resize(entries_.size());
  display_toks_.resize(entries_.size());
  for (uint32_t e = 0; e < entries_.size(); ++e) {
    const Entry& en = entries_[e];
    toks.clear();
    std::vector<std::string> base;
    display_toks_[e] = normalize(en.display);
    for (auto& t : display_toks_[e])
      if (toks.insert(t).second) base.push_back(t);
    for (const auto& al : en.aliases)
      for (auto& t : normalize(al))
        if (toks.insert(t).second) base.push_back(t);
    // one-level alias expansion: bag semantics on the index side
    for (const auto& t : base) {
      if (auto it = aliases_.find(t); it != aliases_.end())
        for (const auto& alt : it->second)
          for (const auto& a : alt) toks.insert(a);
    }
    for (const auto& t : toks) postmap[t].push_back(e);
    entry_toks_[e].assign(toks.begin(), toks.end());
  }

  vocab_.reserve(postmap.size());
  for (auto& kv : postmap) vocab_.push_back(kv.first);
  std::sort(vocab_.begin(), vocab_.end());

  post_off_.assign(vocab_.size() + 1, 0);
  for (size_t v = 0; v < vocab_.size(); ++v) {
    const auto& pl = postmap[vocab_[v]];
    post_off_[v] = (uint32_t)post_flat_.size();
    post_flat_.insert(post_flat_.end(), pl.begin(), pl.end());
  }
  post_off_[vocab_.size()] = (uint32_t)post_flat_.size();

  tri_.reserve(vocab_.size() * 4);
  for (uint32_t v = 0; v < vocab_.size(); ++v)
    for (uint32_t key : trigrams(vocab_[v])) tri_[key].push_back(v);

  estamp_.assign(entries_.size(), 0);
  vstamp_.assign(vocab_.size(), 0);
  vscore_.assign(vocab_.size(), 0.0);
}

// ---------------------------------------------------------------------------
// Query — phase 1: per-atom candidate vocab tokens -> per-(entry, atom) best
// pair quality; phase 2: group/alt evaluation + scoring.
// ---------------------------------------------------------------------------
std::vector<Hit> SearchIndex::query(const std::string& q,
                                    std::optional<double> lat,
                                    std::optional<double> lon,
                                    size_t limit) const {
  std::vector<std::string> qtoks = normalize(q);
  const size_t G = qtoks.size();
  if (G == 0 || entries_.empty() || limit == 0) return {};

  // groups: per query token a list of alternatives; alt = list of atom ids.
  std::unordered_map<std::string, uint32_t> atomid;
  std::vector<std::string> atoms;
  std::vector<std::vector<std::vector<uint32_t>>> groups(G);
  auto intern = [&](const std::string& s) -> uint32_t {
    auto [it, ins] = atomid.emplace(s, (uint32_t)atoms.size());
    if (ins) atoms.push_back(s);
    return it->second;
  };
  for (size_t g = 0; g < G; ++g) {
    groups[g].push_back({intern(qtoks[g])});
    if (auto it = aliases_.find(qtoks[g]); it != aliases_.end())
      for (const auto& alt : it->second) {
        std::vector<uint32_t> aids;
        aids.reserve(alt.size());
        for (const auto& a : alt) aids.push_back(intern(a));
        groups[g].push_back(std::move(aids));
      }
  }
  const size_t A = atoms.size();

  // scratch — doubles, not floats: the parity oracle asserts scores to 1e-9.
  // Rows are lazily zeroed on first touch via estamp_, so no full clear.
  const size_t E = entries_.size();
  const uint64_t qgen = ++gen_;  // touched marker for this query
  if (atom_best_.size() < E * A) atom_best_.resize(E * A);
  std::vector<uint32_t> touched_entries;
  std::vector<uint32_t> touched_vids;
  touched_entries.reserve(1024);
  touched_vids.reserve(256);

  // phase 1 — candidate generation + postings accumulation
  for (size_t ai = 0; ai < A; ++ai) {
    const std::string& x = atoms[ai];
    const size_t lx = x.size();
    const uint64_t agen = ++gen_;
    touched_vids.clear();

    // prefix range over the sorted vocab — all-digit atoms and atoms
    // of 1-2 chars match EXACTLY: '12' is twelve, not 125; 'i' is not
    // 'ii'; a digit string is an identifier, not a stem
    const bool exact_only =
        x.size() <= 2 ||
        std::all_of(x.begin(), x.end(),
                    [](unsigned char c) { return c >= '0' && c <= '9'; });
    auto lo = std::lower_bound(vocab_.begin(), vocab_.end(), x);
    if (exact_only) {
      if (lo != vocab_.end() && *lo == x) {
        uint32_t vid = (uint32_t)(lo - vocab_.begin());
        vstamp_[vid] = agen;
        vscore_[vid] = 1.0;
        touched_vids.push_back(vid);
      }
    } else {
      for (auto it = lo; it != vocab_.end() &&
             it->compare(0, lx, x) == 0; ++it) {
        uint32_t vid = (uint32_t)(it - vocab_.begin());
        vstamp_[vid] = agen;
        vscore_[vid] = (double)lx / (double)it->size();
        touched_vids.push_back(vid);
      }
    }

    // fuzzy candidates via padded-trigram inverted index — never for
    // exact-only atoms ('110001' must not fuzz to '110011')
    if (!exact_only && lx >= 4) {
      const int bound = lx < 8 ? 1 : 2;
      for (uint32_t key : trigrams(x)) {
        auto jt = tri_.find(key);
        if (jt == tri_.end()) continue;
        for (uint32_t vid : jt->second) {
          if (vstamp_[vid] == agen) continue;  // already scored by prefix rule
          const std::string& t = vocab_[vid];
          if (std::abs((int)t.size() - (int)lx) > bound) continue;
          int d = dl_distance(x, t, bound);
          if (d <= bound) {
            vstamp_[vid] = agen;
            vscore_[vid] = 1.0 - (double)d / (double)std::max(lx, t.size());
            touched_vids.push_back(vid);
          }
        }
      }
    }

    for (uint32_t vid : touched_vids) {
      double qv = vscore_[vid];
      for (uint32_t p = post_off_[vid]; p < post_off_[vid + 1]; ++p) {
        uint32_t e = post_flat_[p];
        if (estamp_[e] != qgen) {
          estamp_[e] = qgen;
          std::fill(atom_best_.begin() + (size_t)e * A,
                    atom_best_.begin() + (size_t)e * A + A, 0.0);
          touched_entries.push_back(e);
        }
        double& slot = atom_best_[(size_t)e * A + ai];
        if (qv > slot) slot = qv;
      }
    }
  }

  // phase 2 — group evaluation + scoring
  // Coverage gates (v2/gazetteer.search's tuned rules): at least half the
  // query tokens must cover, and the LEAD query token must cover — the
  // lead rule kills 'X + locality-tail' noise ('haldiram chandni' must be
  // a haldiram hit, not any chandni hit).
  const int need = std::max(1, (int)std::ceil((double)G * 0.5));
  std::vector<Hit> res;
  res.reserve(touched_entries.size() < limit ? touched_entries.size() : limit);
  const bool has_bias = lat.has_value() && lon.has_value();
  for (uint32_t e : touched_entries) {
    const double* row = &atom_best_[(size_t)e * A];
    double sum_q = 0.0;
    double lead_gq = -1.0;
    int matched = 0;
    size_t gi = 0;
    bool fuzzy = false;
    for (const auto& g : groups) {
      double gq = 0.0;
      for (const auto& alt : g) {
        if (alt.empty()) continue;
        double aq = row[alt[0]];
        for (size_t k = 1; k < alt.size(); ++k)
          aq = std::min(aq, (double)row[alt[k]]);
        if (aq > gq) gq = aq;
      }
      if (gi == 0) lead_gq = gq;
      sum_q += gq;
      if (gq > 0) {
        ++matched;
        // a covered group with no entry token starting with a query atom
        // was reached only by DL distance — the match is fuzzy
        bool prefix_hit = false;
        for (const auto& alt : g) {
          for (uint32_t aid : alt) {
            const std::string& a = atoms[aid];
            for (const auto& t : entry_toks_[e]) {
              if (t.size() >= a.size() && t.compare(0, a.size(), a) == 0) {
                prefix_hit = true;
                break;
              }
            }
            if (prefix_hit) break;
          }
          if (prefix_hit) break;
        }
        if (!prefix_hit) fuzzy = true;
      }
      ++gi;
    }
    if (matched < need || lead_gq <= 0.0) continue;
    const Entry& en = entries_[e];
    double pq = sum_q / (double)G;
    double cov = (double)matched / (double)G;
    // display precision — share of display tokens explained by a query
    // atom (prefix either direction); breaks same-coverage ties toward
    // names the query fully explains (gazetteer W_PREC)
    double prec = 0.0;
    const auto& dtoks = display_toks_[e];
    if (!dtoks.empty()) {
      int covd = 0;
      for (const auto& t : dtoks) {
        for (const auto& a : atoms) {
          if ((t.size() >= a.size() && t.compare(0, a.size(), a) == 0) ||
              (a.size() >= t.size() && a.compare(0, t.size(), t) == 0)) {
            ++covd;
            break;
          }
        }
      }
      prec = (double)covd / (double)dtoks.size();
    }
    // leading-prefix bonus — the display is a strict leading token
    // prefix of the query ('beta 2' inside 'beta 2 greater noida'):
    // this row IS the named thing, not a POI containing its words.
    // Folded into the w5 term alongside display precision.
    const bool leadpref =
        !dtoks.empty() && dtoks.size() < G &&
        std::equal(dtoks.begin(), dtoks.end(), qtoks.begin());
    double dist = 0.0;
    if (has_bias) dist = haversine_km(*lat, *lon, en.lat, en.lon);
    double score = w_.w1 * pq + w_.w2 * cov + w_.w3 * en.popularity +
                   w_.w5 * (prec + (leadpref ? 1.0 : 0.0)) -
                   w_.w4 * std::log1p(dist);
    res.push_back(Hit{score, e, cov, fuzzy});
  }

  auto better = [&](const Hit& a, const Hit& b) {
    if (a.score != b.score) return a.score > b.score;
    if (entries_[a.eidx].id != entries_[b.eidx].id)
      return entries_[a.eidx].id < entries_[b.eidx].id;
    return a.eidx < b.eidx;
  };
  const size_t k = std::min(limit, res.size());
  std::partial_sort(res.begin(), res.begin() + k, res.end(), better);
  res.resize(k);
  return res;
}

}  // namespace alive
