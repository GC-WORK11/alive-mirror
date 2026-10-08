// Alive — T1 fuzzy search index (alive_core).
//
// Query semantics — kept bit-identical with server/alive_core_ref.py
// (the parity oracle). Any change here must be mirrored there.
//
// Normalization: lowercase, ASCII-fold (NFKD -> drop non-ASCII), strip
// punctuation, single-level alias/abbreviation expansion both at index
// time (entry tokens) and query time (token alternatives).
//
// Structures: sorted vocab with prefix ranges (binary search) + padded-
// trigram inverted index for fuzzy candidates. Fuzzy bound:
// Damerau-Levenshtein <= 1 for atoms >= 4 chars, <= 2 for >= 8 chars.
//
// Scoring: prefix_quality*w1 + token_coverage*w2 + popularity*w3
//          - log1p(distance_km)*w4

#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <unordered_map>
#include <vector>

namespace alive {

struct Entry {
  uint32_t id = 0;
  std::string display;
  std::vector<std::string> aliases;
  std::string category;
  double lat = 0.0;
  double lon = 0.0;
  double popularity = 0.0;
};

// normalized token -> alternatives; each alternative is a token sequence.
using AliasMap =
    std::unordered_map<std::string, std::vector<std::vector<std::string>>>;

struct Weights {
  double w1 = 1.0;   // prefix_quality
  double w2 = 1.0;   // token_coverage
  double w3 = 0.5;   // popularity
  double w4 = 0.15;  // log1p(distance_km)
  double w5 = 0.5;   // display precision (gazetteer W_PREC)
};

struct Hit {
  double score = 0.0;
  uint32_t eidx = 0;  // index into entries_
  double cov = 0.0;   // matched query-token groups / groups
  bool fuzzy = false; // a matched group had no prefix-covered token
};

class SearchIndex {
 public:
  SearchIndex(std::vector<Entry> entries, AliasMap aliases, Weights w);

  // Sorted (score desc, id asc, eidx asc) top-`limit` hits.
  std::vector<Hit> query(const std::string& q, std::optional<double> lat,
                         std::optional<double> lon, size_t limit) const;

  size_t size() const { return entries_.size(); }
  const Entry& entry(size_t i) const { return entries_[i]; }

 private:
  std::vector<Entry> entries_;
  AliasMap aliases_;
  Weights w_;

  std::vector<std::string> vocab_;      // sorted unique tokens
  std::vector<uint32_t> post_flat_;     // concatenated postings (entry idx)
  std::vector<uint32_t> post_off_;      // offsets, size vocab_.size()+1
  std::unordered_map<uint32_t, std::vector<uint32_t>> tri_;  // trigram->vids
  // per-entry match tokens (display + alias + alias-expanded atoms) —
  // the same set that built the postings; needed for the fuzzy flag
  std::vector<std::vector<std::string>> entry_toks_;
  // per-entry display tokens (normalize(display)) — precision term
  std::vector<std::vector<std::string>> display_toks_;

  // query scratch — generation-stamped so repeated queries never re-zero
  mutable std::vector<double> atom_best_;    // [e*A + atom], row = per-entry
  mutable std::vector<uint64_t> estamp_;     // entry touched, per query
  mutable std::vector<uint64_t> vstamp_;     // vocab scored, per atom
  mutable std::vector<double> vscore_;
  mutable uint64_t gen_ = 0;
};

// Split into normalized [a-z0-9] tokens (identical to ref normalize()).
std::vector<std::string> normalize(const std::string& s);

// True Damerau-Levenshtein. `bound` only prunes |len diff| > bound.
int dl_distance(const std::string& a, const std::string& b, int bound);

double haversine_km(double lat1, double lon1, double lat2, double lon2);

}  // namespace alive
