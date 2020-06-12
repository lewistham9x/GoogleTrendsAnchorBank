# TODO:
#   add plots
# Make anchor banks for 
# 1.) US, Sweden, Italy, Switzerland
# 2.) Germany, UK, Spain

import copy
import ast
import codecs
import os
import pickle
import random
import time
import math
import warnings

import networkx as nx
import numpy as np
import pandas as pd
from pytrends.request import TrendReq
from tqdm import tqdm

class GTAB:

    def __init__(self, ptrends_config = None, gtab_config = None, conn_config = None, blacklist = None, use_proxies = False):
        """
            Initializes the GTAB instance.

            Input parameters:
                ptrends_config - a dictionary containing the configuration parameters for the pytrends library when building the payload (i.e. timeframe and geo).
                gtab_config - a dictionary containing the configuration parameters for the GTAB methodology when making the connection.
                conn_config - a dictionary containing the configuration parameters for the connection (e.g. proxies, timeout, retries...).

            If any parameter is None, the corresponding file in the directory "./config/" is taken. It should contain a single line with the corresponding config dictionary.
        """

        if ptrends_config == None:
            with open(os.path.join("config", "ptrends.config"), "r") as f_conf:
                self.PTRENDS_CONFIG = ast.literal_eval(f_conf.readline())
        else: 
            self.PTRENDS_CONFIG = ptrends_config

        if gtab_config == None:
            with open(os.path.join("config", "gtab.config"), "r") as f_conf:
                self.GTAB_CONFIG = ast.literal_eval(f_conf.readline())
        else: 
            self.GTAB_CONFIG = gtab_config

        if conn_config == None:
            with open(os.path.join("config", "conn.config"), "r") as f_conf:
                self.CONN_CONFIG = ast.literal_eval(f_conf.readline())
        else:
            self.CONN_CONFIG = conn_config
            
        if blacklist == None:
            with open(os.path.join("config", "blacklist.config"), "r") as f_conf:
                self.BLACKLIST = ast.literal_eval(f_conf.readline()) 
        else:
            self.BLACKLIST = blacklist

        with open(os.path.join("data", "anchor_candidates.tsv"), 'r', encoding = 'utf-8') as f_anchor_set:
            self.ANCHOR_CANDIDATE_SET = pd.read_csv(f_anchor_set, sep = '\t')

        self.ANCHOR_CANDIDATE_SET.rename(index = {k: v for k, v in enumerate(list(self.ANCHOR_CANDIDATE_SET['mid']))}, inplace = True)
        mask = (np.array(self.ANCHOR_CANDIDATE_SET['is_dish'] == 1) | np.array(self.ANCHOR_CANDIDATE_SET['is_food'] == 1))
        self.ANCHOR_CANDIDATE_SET = self.ANCHOR_CANDIDATE_SET[mask]
        self.HITRAFFIC = {'Facebook': '/m/02y1vz', 'Yahoo!': '/m/019rl6', 'Twitter': '/m/0289n8t',  'Reddit': '/m/0b2334', 'LinkedIn': '/m/03vgrr' , 'Airbnb': '/m/010qmszp'}#, 'Coca-Cola': '/m/01yvs'}
        self._init_done = False
        
        if use_proxies:
            self.ptrends = TrendReq(hl='en-US', **self.CONN_CONFIG)
        else:
            self.ptrends = TrendReq(hl='en-US', timeout = (20, 20))

    ## --- UTILITY METHODS --- #
    def _query_google(self, keywords = ["Keywords"]):
        time.sleep(self.GTAB_CONFIG['sleep'])
        if type(keywords) == str:
            keywords = [keywords]
    
        if len(keywords) > 5:
            raise ValueError("Query keywords must be less than 5.")

        self.ptrends.build_payload(kw_list = keywords, **self.PTRENDS_CONFIG)
        return(self.ptrends.interest_over_time())

    def _is_blacklisted(self, keyword):
        return not keyword in self.BLACKLIST

    def _check_keyword(self, keyword):
        try:
            self._query_google(keywords = keyword)
            return self._is_blacklisted(keyword)
        except Exception as e:
            print(e)
            if "response" in dir(e):
                if e.response.status_code == 429:
                    raise ConnectionError("Code 429: Query limit reached on this IP!")
            self._log_con.write(f"Bad keyword '{keyword}', because {str(e)}`\n")
            return False
    
    def _check_ts(self, ts):
        return ts.max().max() >= self.GTAB_CONFIG['thresh_offline']

    def _check_group(self, val):
        ret = None
        idx = None
        if sum(val.max() < self.GTAB_CONFIG['thresh_offline']) == 4: # try with 3 as well
            ret = val.max().idxmax()
            idx = np.where(val.columns == ret)
        return ret, idx

    def _find_outliers(self, gres):
        ret = set()
        for _, val in gres.items():
            # if any(val.max() < self.GTAB_CONFIG['thresh_offline']):
            #     ret.add(val.max().idxmax())
            if sum(val.max() < self.GTAB_CONFIG['thresh_offline']) == 4: # try with 3 as well
                ret.add(val.max().idxmax())

        return list(ret)
        



    ## --- ANCHOR BANK METHODS --- ##
    def _get_google_results(self):

        # TODO TEST GEO
        # fpath = os.path.join("data", "google_results_RTEST.pkl") # same nodes are queried as the R implementation
        # fpath = os.path.join("data", "google_test_autotest7.pkl")
        # fpath = os.path.join("data", "google_test_autotest_time2.pkl")
        # fpath = os.path.join("data", "google_test_autotest_big.pkl")
        # The following comment block should be used instead of the above line, but we need to find a parameter combination that produces a valid anchor bank automatically.

        if self.GTAB_CONFIG["anchor_file"].strip() != "" and self.GTAB_CONFIG["anchor_file"] != None:
            fpath = os.path.join("data", "google_results", self.GTAB_CONFIG["anchor_file"])
            fpath_keywords = os.path.join("data", "google_keywords", self.GTAB_CONFIG["anchor_file"])
        elif self.PTRENDS_CONFIG['geo'].strip() != "":
            fpath = os.path.join("data", "google_results", f"google_results_{self.GTAB_CONFIG['num_anchor_candidates']}_{self.GTAB_CONFIG['num_anchors']}_t{self.GTAB_CONFIG['thresh_offline']}_{self.PTRENDS_CONFIG['geo']}.pkl")
            fpath_keywords = os.path.join("data", "google_keywords", f"google_keywords_{self.GTAB_CONFIG['num_anchor_candidates']}_{self.GTAB_CONFIG['num_anchors']}_t{self.GTAB_CONFIG['thresh_offline']}_{self.PTRENDS_CONFIG['geo']}.pkl")
        else:
            fpath = os.path.join("data", "google_results", f"google_results_{self.GTAB_CONFIG['num_anchor_candidates']}_{self.GTAB_CONFIG['num_anchors']}_t{self.GTAB_CONFIG['thresh_offline']}_global.pkl")
            fpath_keywords = os.path.join("data", "google_keywords" , f"google_keywords_{self.GTAB_CONFIG['num_anchor_candidates']}_{self.GTAB_CONFIG['num_anchors']}_t{self.GTAB_CONFIG['thresh_offline']}_global.pkl")


        if os.path.exists(fpath):
            print(f"Loading google results from {fpath}...") 
            with open(fpath, 'rb') as f_in:
                ret = pickle.load(f_in)
            return ret
        else:
            N = self.GTAB_CONFIG['num_anchor_candidates']
            K = self.GTAB_CONFIG['num_anchors']

            ## --- Get stratified samples, 1 per stratum. --- ##
            if self.GTAB_CONFIG["kw_file"] == None or self.GTAB_CONFIG["kw_file"].strip() == "":
                print("Sampling keywords...")
                random.seed(self.GTAB_CONFIG['seed'])
                samples = []
                for j in range(K):
                    start_idx = (j * N) // K
                    end_idx = (((j+1) * N) // K) - 1
                    s1 = random.randint(start_idx, end_idx)
                    samples.append(self.ANCHOR_CANDIDATE_SET.index[s1])

                keywords = list(self.HITRAFFIC.values()) + samples
                keywords = [k for k in tqdm(keywords, total = len(keywords)) if self._check_keyword(k)]

            else:
                print(f"Getting keywords from {self.GTAB_CONFIG['kw_file']}")
                with open(self.GTAB_CONFIG['kw_file'], 'rb') as f_kw_in:
                    keywords = pickle.load(f_kw_in)         
                keywords = [k for k in tqdm(keywords, total = len(keywords)) if self._is_blacklisted(k)]

            with open(fpath_keywords, 'wb') as f_out_keywords:
                pickle.dump(keywords, f_out_keywords, protocol=4)
            
            keywords = np.array(keywords)
            
            ## --- Query google on keywords and dump the file. --- ##
            print("Querying google...")
    
        
            ret = dict()                

            max_i = 0
            i = 0
            lim = len(keywords) - 5 + 1
            prog_bar = tqdm(total = lim)

            while True:
                if i >= lim:
                    break
                
                try:
                    df_query = self._query_google(keywords = keywords[i:i+5]).iloc[:, 0:5]
                except Exception as e:
                    if "response" in dir(e):
                        if e.response.status_code == 429:
                            c = input("Quota reached! Please change IP and press any key to continue.")
                            
                            df_query = self._query_google(keywords = keywords[i:i+5]).iloc[:, 0:5]
                        else:
                            print(str(e))

                outlier_name, outlier_idx = self._check_group(df_query)


                if outlier_name == None:
                    ret[i] = df_query
                else:
                    self._log_con.write(f"Removed bad keyword: {str(outlier_name)}\n")
                    print(f"\nRemoved bad keyword: {str(outlier_name)}\n")
                    print(df_query)
                    # print(outlier_idx[0][0])
                    outlier_idx = outlier_idx[0][0]
                    # print(keywords)
                    keywords = np.delete(keywords, i + outlier_idx)
                    # print(keywords)
                    curr_i = i
                    i += outlier_idx - 5
                    lim -= 1
                    for t_i in range(i+1, curr_i):
                        # print(t_i, end = " ")
                        if t_i in ret:
                            # print(ret[t_i])
                            del ret[t_i]
                    prog_bar.update(0)

                i += 1
                max_i = max(i, max_i)
                if i == max_i:
                    prog_bar.update(1)

            if max_i > lim:
                print(max_i)
                print(lim)
                raise ValueError("RIP")
            prog_bar.close()

            # object id sanity check
            assert id(ret[0]) != id(ret[1])

            with open(fpath, 'wb') as f_out:
                pickle.dump(ret, f_out, protocol=4)

            return(ret)

    def _compute_max_ratios(self, google_results):
        t_anchors = []
        t_v1 = []
        t_v2 = []
        t_ratios_vec = []
        inverse_ratios = dict()

        for _, val in google_results.items():
            for j in range(val.shape[1]-1):
                for k in range(j + 1, val.shape[1]):
                    if(self._check_ts(val.iloc[:, j]) and self._check_ts(val.iloc[:, k])):

                        t_anchors.append(val.columns[0]) # first element of group
                        t_v1.append(val.columns[j])
                        t_v2.append(val.columns[k])

                        vpair = " ".join([val.columns[j], val.columns[k]])
                        t_ratio = val.iloc[:, j].max().max() / val.iloc[:, k].max().max()

                        if vpair not in inverse_ratios.keys():
                            inverse_ratios[vpair] = [0, 0] # <, >
                        if t_ratio < 1.0:
                            inverse_ratios[vpair][0] += 1
                        elif t_ratio > 1.0:
                            inverse_ratios[vpair][1] += 1

                        t_ratios_vec.append(t_ratio)
                        

        # filter where <>1 inversion happens
        anchors = []
        v1 = []
        v2 = []
        ratios_vec = []

        for j in range(len(t_ratios_vec)):
            vpair = " ".join([t_v1[j], t_v2[j]])

            if inverse_ratios[vpair][0] > 0 and inverse_ratios[vpair][1] > 0:
                if inverse_ratios[vpair][0] >= inverse_ratios[vpair][1]:
                    if t_ratios_vec[j] < 1.0:
                        anchors.append(t_anchors[j])
                        v1.append(t_v1[j])
                        v2.append(t_v2[j])
                        ratios_vec.append(t_ratios_vec[j])
                else:
                    if t_ratios_vec[j] > 1.0:
                        anchors.append(t_anchors[j])
                        v1.append(t_v1[j])
                        v2.append(t_v2[j])
                        ratios_vec.append(t_ratios_vec[j])
            else:
                anchors.append(t_anchors[j])
                v1.append(t_v1[j])
                v2.append(t_v2[j])
                ratios_vec.append(t_ratios_vec[j])
        
            
        # If ratio > 1, flip positions and change ratio value to 1/ratio.
        for j in range(len(ratios_vec)):
            vpair = " ".join([v1[j], v2[j]])
            if ratios_vec[j] > 1.0: # and not inverse_ratios[vpair][0] or not inverse_ratios[vpair][1]:
                v1[j], v2[j] = v2[j], v1[j]
                ratios_vec[j] = 1./ratios_vec[j]
        
        # Handle edge-case where ratio == 1
        pair_names = [" ".join(el) for el in zip(np.array(v1)[np.array(ratios_vec) < 1.0], np.array(v2)[np.array(ratios_vec) < 1.0])]
        for i in range(len(ratios_vec)):
            if math.isclose(ratios_vec[i], 1.0):
                if " ".join([v1[i], v2[i]]) in pair_names:
                    continue
                elif " ".join([v2[i], v1[i]]) in pair_names:
                    v1[i], v2[i] = v2[i], v1[i]
                else:
                    tmp = sorted((v1[i], v2[i]))
                    v1[i] = tmp[0]
                    v2[i] = tmp[1]

        assert len(ratios_vec) == len(v1) == len(v2) == len(anchors)
        df_ratios = pd.DataFrame({"anchor": anchors, "v1": v1, "v2": v2, "ratio": ratios_vec})
        df_ratios_aggr = df_ratios.groupby(['v1', 'v2']).agg({"ratio": ['mean', 'std']})
        df_ratios_aggr.columns = df_ratios_aggr.columns.droplevel(0)
        df_ratios_aggr.reset_index(inplace = True)
        df_ratios_aggr.set_index(df_ratios_aggr.apply(lambda x: " ".join([x[0], x[1]]), axis = 1), inplace=True)

        return df_ratios_aggr

    def _infer_all_ratios(self, ratios_aggr):
        
        vcore = list(set().union(ratios_aggr['v1'], ratios_aggr['v2']))
        vcore.sort()
        W0 = pd.DataFrame(np.zeros((len(vcore), len(vcore))), index = vcore, columns = vcore, dtype=float)
        A0 = pd.DataFrame(np.zeros((len(vcore), len(vcore))), index = vcore, columns = vcore, dtype=float)
        
        for u in vcore:
            for v in vcore:
                ratio = np.nan
                if u == v:
                    ratio = 1.0
                else:
                    key = " ".join([u, v])
                    if key in ratios_aggr.index:
                        ratio = ratios_aggr.loc[key, 'mean']
                if np.isfinite(ratio):
                    W0.loc[u, v] = ratio
                    W0.loc[v, u] = 1./ratio
                    A0.loc[u, v] = 1
                    A0.loc[v, u] = 1

        W = copy.deepcopy(W0)
        A = copy.deepcopy(A0)

        while True:
            AA = A.dot(A)
            WW = A * W + (1-A) * ((W.dot(W)) / AA)
            WW.fillna(0.0, inplace = True)
            W = copy.deepcopy(WW)
            A_old = copy.deepcopy(A)

            # object id sanity check
            assert id(W) != id(WW)
            assert (W == WW).all().all()

            A = (AA > 0).astype(int)

            if (A == A_old).all().all():
                break

        return W
        
    ## --- "EXPOSED" METHODS --- ##
    def init(self, verbose = False):
        """
        Initializes the GTAB instance according to the config files found in the directory "./config/".
        """

        self._log_con = open(os.path.join("log", f"log_{self.GTAB_CONFIG['num_anchor_candidates']}_{self.GTAB_CONFIG['num_anchors']}_t{self.GTAB_CONFIG['thresh_offline']}_{self.PTRENDS_CONFIG['geo']}.txt"), 'w')
        # self._log_con = open("log.txt", "w")

        if verbose:
            print(self.GTAB_CONFIG)
            print(self.PTRENDS_CONFIG)
        google_results = self._get_google_results() 
        print(f"Total queries (groups of 5 keywords): {len(google_results)}")
        time_series = pd.concat(google_results, axis=1)
        ratios = self._compute_max_ratios(google_results)   
        G = nx.convert_matrix.from_pandas_edgelist(ratios, 'v1', 'v2', create_using = nx.DiGraph)

        if not nx.is_directed_acyclic_graph(G):
            warnings.warn("Directed graph is not acyclic!") 
            print(f"Cycles are: {list(nx.algorithms.cycles.simple_cycles(G))}")
            self._log_con.write(f"Cycles are: {list(nx.algorithms.cycles.simple_cycles(G))}\n")
        if not nx.is_weakly_connected(G):
            print(f"Num. connected components: {nx.number_connected_components(nx.Graph(G))}")
            warnings.warn("Directed graph is not connected!")

        W = self._infer_all_ratios(ratios)
        err = np.nanmax(np.abs(1 - W * W.transpose()))

        # colSums equivalent is df.sum(axis = 0)
        ref_anchor = W[(W > 1).sum(axis = 0) == 0].index[0]
        
        if len(ref_anchor) > 1 and type(ref_anchor) is not str and type(ref_anchor) is not np.str_: 
            # print(ref_anchor)
            # print(type(ref_anchor))
            ref_anchor = (W.loc[:, ref_anchor] > 0).sum(axis = 0).idxmax()[0]

        self.google_results = google_results
        self.G = G
        self.ref_anchor = ref_anchor
        self.err = err
        self.W = W
        self.calib_max_vol = W.loc[:, ref_anchor].sort_values()
        self.ratios = ratios    
        self.time_series = time_series
        self._init_done = True

        self._log_con.close()
        print("Done.")


    def new_query(self, keyword):

        """
        Request a new GTrends query and calibrate it with the GTAB instance.
        Input parameters:
            keyword - string containing a single query.
        Returns a dictionary containing:
            ratio - the computed ratio.
            ts - the calibrated time series for the keyword.
            iter - the number of iterations needed by the binary search.

            If not able to calibrate, returns -1.
            
        """
        if not self._init_done:
            print("Must use GTAB.init() to initialize first!")
            return None

        anchors = tuple(self.calib_max_vol.index)
        lo = 0
        hi = len(self.calib_max_vol)
        cnt = 0

        while hi >= lo:
            mid = (hi + lo) // 2
            anchor = anchors[mid]

            try:
                ts = self._query_google(keywords = [anchor, keyword]).iloc[:, 0:2]
            except Exception as e:
                print(f"Google query failed because: {str(e)}")
                break

            max_anchor = ts.loc[:, anchor].max()
            max_keyword = ts.loc[:, keyword].max()

            if max_keyword >= self.GTAB_CONFIG['thresh_offline'] and max_anchor >= self.GTAB_CONFIG['thresh_offline']:
                ratio = self.calib_max_vol[anchor] * (max_keyword / max_anchor)
                ts_keyword = ts.loc[:, keyword] / max_keyword * ratio
                return {"ratio": ratio, "ts": ts_keyword, "iter": cnt}
            elif max_keyword < self.GTAB_CONFIG['thresh_offline']:
                hi = mid - 1
            else:
                lo = mid + 1 

            cnt += 1

        print(f"Unable to calibrate keyword {keyword}!")
        return -1

if __name__ == '__main__':

    t = GTAB(use_proxies = False)
    t.init(verbose = True)
   