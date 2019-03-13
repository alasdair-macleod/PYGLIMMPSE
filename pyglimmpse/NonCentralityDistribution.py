#!/usr/bin/env python

import numpy as np
from scipy import optimize
from scipy.stats import f

from pyglimmpse.WeightedSumOfNoncentralChiSquaresDistribution import WeightedSumOfNoncentralChiSquaresDistribution
from pyglimmpse.constants import Constants
from pyglimmpse.probf import probf

""" generated source for module NonCentralityDistribution """
from pyglimmpse.chisquareterm import ChiSquareTerm

class NonCentralityDistribution(object):
    """ generated source for class NonCentralityDistribution """
    NOT_POSITIVE_DEFINITE = "Unfortunately, there is no solution for this combination of input parameters. " + "A matrix that arose during the computation is not positive definite. " + "It may be possible to reduce expected covariate/response correlations " + "and obtain a soluble combination."
    MAX_ITERATIONS = 10000
    ACCURACY = 0.001

    #  intermediate forms
    T1 = None
    FT1 = None
    S = None
    mzSq = None
    H1 = float()
    H0 = 0
    qF = int()
    a = int()
    N = float()
    sEigenValues = []
    sStar = 0

    #  indicates if an "exact" cdf should be calculated via Davie's algorithm or
    #  with the Satterthwaite approximation from Glueck & Muller
    exact = bool()

    # 
    #      * Create a non-centrality distribution for the specified inputs.
    #      * @param params GLMM input parameters
    #      * @param exact if true, Davie's algorithm will be used to compute the cdf,
    #      * otherwise a Satterthwaite style approximation is used.
    #      * @throws IllegalArgumentException
    #      
    def __init__(self, test, FEssence, perGroupN, CFixed, CGaussian, thetaDiff, sigmaStar, stddevG, exact):
        """ generated source for method __init__ """
        self.initialize(
            test=test,
            FEssence=FEssence,
            perGroupN=perGroupN,
            Cfixed=CFixed,
            CGaussian=CGaussian,
            thetaDiff=thetaDiff,
            sigmaStar=sigmaStar,
            stddevG = stddevG,
            exact=exact)

    # 
    #      * Pre-calculate intermediate matrices, perform setup, etc.
    #      
    def initialize(self, test, FEssence, perGroupN, Cfixed, CGaussian, thetaDiff, sigmaStar, stddevG, exact):
        """ generated source for method initialize """
        #  reset member variables
        self.T1 = None
        self.FT1 = None
        self.S = None
        self.mzSq = None
        self.H0 = 0
        self.sStar = 0
        self.N = float(FEssence.shape[0]) * perGroupN
        self.exact = exact
        self.errors = []
        try:
            #  TODO: need to calculate H0, need to adjust H1 for Unirep
            #  get design matrix for fixed parameters only
            #self.qF = FEssence.getColumnDimension()
            self.qF = FEssence.shape[1]
            #  a = CFixedRand.getCombinedMatrix().getRowDimension();
            #  get fixed contrasts

            #  build intermediate terms h1, S
            FtFinverse = np.linalg.inv(FEssence.T * FEssence)
            PPt = Cfixed * FtFinverse * (1 / perGroupN) * Cfixed.T
            self.T1 = self.forceSymmetric(np.linalg.inv(PPt))
            self.FT1 = np.linalg.cholesky(self.T1)
            #calculate theta difference
            # TODO I think CRand should already be an array
            # C = np.concatenate((np.array(CFixed), np.array(CRand)), axis=1)
            #TODO: specific to HLT or UNIREP
            sigmaStarInverse = self.getSigmaStarInverse(sigmaStar, test)
            H1matrix = thetaDiff.T * self.T1 * thetaDiff * sigmaStarInverse
            self.H1 = np.trace(H1matrix)
            # Matrix which represents the non-centrality parameter as a linear combination of chi-squared r.v.'s.
            self.S = self.FT1.T * thetaDiff * sigmaStarInverse * thetaDiff.T * self.FT1 * (1 / self.H1)
            # We use the S matrix to generate the F-critical, numerical df's, and denominator df's
            # for a central F distribution.  The resulting F distribution is used as an approximation
            # for the distribution of the non-centrality parameter.
            # See formulas 18-21 and A8,A10 from Glueck & Muller (2003) for details.
            self.sEigenValues, svecs = np.linalg.eig(self.S)
            self.sEigenValues = self.sEigenValues[::-1]
            svecs = np.flip(svecs, 1)
            svec = np.matrix(svecs).T

            if len(self.sEigenValues) > 0:
                self.H0 = self.H1 * (1 - self.sEigenValues[0])
            if self.H0 <= 0:
                self.H0 = 0

            for value in self.sEigenValues:
                if value > 0:
                    self.sStar += 1
            # TODO: throw error if sStar is <= 0
            # TODO: NO: throw error if sStar != sEigenValues.length instead???
            # create square matrix using these
            self.mzSq = svec * self.FT1.T * CGaussian * (1 / stddevG)
            i = 0
            while i < self.mzSq.shape[0]:
                j = 0
                #while j < self.mzSq.getColumnDimension():
                while j <  self.mzSq.shape[1]:
                    entry = self.mzSq[i, j]
                    self.mzSq[i, j] = entry * entry
                    j += 1
                i += 1
        except Exception as e:
            raise e

    def setPerGroupSampleSize(self, perGroupN):
        """ generated source for method setPerGroupSampleSize """
        self.initialize(self.test, self.FEssence, self.FtFinverse, perGroupN, self.CFixed, self.CRand, self.U, self.thetaNull, self.beta, self.sigmaError, self.sigmaG, self.exact)

    def setBeta(self, beta):
        """ generated source for method setBeta """
        self.initialize(self.test, self.FEssence, self.FtFinverse, self.perGroupN, self.CFixed, self.CRand, self.U, self.thetaNull, beta, self.sigmaError, self.sigmaG, self.exact)

    def cdf(self, w):
        """ generated source for method cdf """
        if self.H1 <= 0 or w <= self.H0:
            return 0
        if self.H1 - w <= 0:
            return 1
        chiSquareTerms = []

        try:
            b0 = 1 - w / self.H1
            m1Positive = 0
            m1Negative = 0
            m2Positive = 0
            m2Negative = 0

            numPositive = 0
            numNegative = 0
            lastPositiveNoncentrality = 0  # for special cases
            lastNegativeNoncentrality = 0

            nu = self.N - self.qF
            lambda_ = b0
            delta = 0
            chiSquareTerms.append(ChiSquareTerm(lambda_, nu, delta))
            # add in the first chi-squared term in the estimate of the non-centrality
            # (expressed as a sum of weighted chi-squared r.v.s)
            # initial chi-square term is central (delta=0) with N-qf df, and lambda = b0
            if lambda_ > 0:
                # positive terms
                numPositive += 1
                lastPositiveNoncentrality = delta
                m1Positive += lambda_ * (nu + delta)
                m2Positive += lambda_ * lambda_ * 2 * (nu + 2 * delta)
            elif lambda_ < 0:
                # negative terms - we take absolute value of lambda where needed
                numNegative += 1
                lastNegativeNoncentrality = delta
                m1Negative += -1 * lambda_ * (nu + delta)
                m2Negative += lambda_ * lambda_ * 2 * (nu + 2 * delta)
            # accumulate the remaining terms
            k = 0
            while k < self.sStar:
                if k < self.sStar:
                    # for k = 1 (well, 0 in java array terms and 1 in the paper) to sStar, chi-square term is
                    # non-central (delta = mz^2), 1 df, lambda = (b0 - kth eigen value of S)
                    nu = 1
                    lambda_ = b0 - self.sEigenValues[k]
                    delta = self.mzSq[k, 0]
                    chiSquareTerms.append(ChiSquareTerm(lambda_, nu, delta))
                else:
                    # for k = sStar+1 to a, chi-sqaure term is non-central (delta = mz^2), 1 df,
                    # lambda = b0
                    nu = 1
                    lambda_ = b0
                    delta = self.mzSq[k, 0]
                    chiSquareTerms.add(ChiSquareTerm(lambda_, nu, delta))
                # accumulate terms
                if lambda_ > 0:
                    # positive terms
                    numPositive += 1
                    lastPositiveNoncentrality = delta
                    m1Positive += lambda_ * (nu + delta)
                    m2Positive += lambda_ * lambda_ * 2 * (nu + 2 * delta)
                elif lambda_ < 0:
                    # negative terms - we take absolute value of lambda where needed
                    numNegative += 1
                    lastNegativeNoncentrality = delta
                    m1Negative += -1 * lambda_ * (nu + delta)
                    m2Negative += lambda_ * lambda_ * 2 * (nu + 2 * delta)
                k += 1
                # Note, we deliberately ignore terms for which lambda == 0
            # handle special cases
            if numNegative == 0:
                return 0
            if numPositive == 0:
                return 1
            # handle special cases
            if numNegative == 1 and numPositive == 1:
                Nstar = self.N - self.qF + self.a - 1
                Fstar = w / (Nstar * (self.H1 - w))
                if lastPositiveNoncentrality >= 0 and lastNegativeNoncentrality == 0:
                    return probf(fcrit=Fstar,
                                 df1=Nstar,
                                 df2=1,
                                 noncen=lastPositiveNoncentrality)
                elif lastPositiveNoncentrality == 0 and lastNegativeNoncentrality > 0:
                    # print("fcrit", 1 / Fstar)
                    # print("df1", 1)
                    # print("df2", Nstar)
                    # print("omega", lastNegativeNoncentrality)
                    # print("RUN _PROBF(PROB, FMETHOD, ", 1 / Fstar,", ",1,", ",Nstar,", ",lastNegativeNoncentrality,");")
                    prob, method = probf(fcrit=1 / Fstar,
                          df1=1,
                          df2=Nstar,
                          noncen=lastNegativeNoncentrality)
                    return 1 - prob
            if self.exact:
                dist = WeightedSumOfNoncentralChiSquaresDistribution(chiSquareTerms, 0.0, 0.001)
                return dist.cdf(0)
            else:
                # handle general case - Satterthwaite approximation
                nuStarPositive = 2 * (m1Positive * m1Positive) / m2Positive
                nuStarNegative = 2 * (m1Negative * m1Negative) / m2Negative
                lambdaStarPositive = m2Positive / (2 * m1Positive)
                lambdaStarNegative = m2Negative / (2 * m1Negative)

                # create a central F to approximate the distribution of the non-centrality parameter
                # return power based on the non-central F
                x = (nuStarNegative * lambdaStarNegative) / (nuStarPositive * lambdaStarPositive)
                return f(x, nuStarPositive, nuStarNegative)
        except Exception as e:
            print("exiting cdf abnormally", e)
            raise Exception(e)

    def inverseCDF(self, quantile):
        """ generated source for method inverseCDF """
        if self.H1 <= 0:
            return 0
        quantFunc = lambda n: quantile -  self.cdf(n)
        try:
            return optimize.bisect(quantFunc, self.H0, self.H1)
        except Exception as e:
            raise Exception("Failed to determine non-centrality quantile: " + e.args[0])

    def NonCentralityQuantileFunction(self, quantile):
        """ generated source for class NonCentralityQuantileFunction """
        try:
            return self.cdf(n) - quantile
        except Exception as pe:
            raise Exception(pe, pe)

    def getSigmaStarInverse(self, sigma_star, test):
        """ generated source for method getSigmaStarInverse """
        if not self.isPositiveDefinite(sigma_star):
            self.errors.append(Constants.ERR_NOT_POSITIVE_DEFINITE)
        if test == Constants.HLT or Constants.HLT.value:
            return np.linalg.inv(sigma_star)
        else:
            # stat should only be UNIREP (uncorrected, box, GG, or HF) at this point
            # (exception is thrown by valdiateParams otherwise)
            b = sigma_star.shape[1]
            # get discrepancy from sphericity for unirep test
            sigmaStarTrace = np.trace(sigma_star)
            sigmaStarSquaredTrace = np.trace(sigma_star * sigma_star)
            epsilon = (sigmaStarTrace * sigmaStarTrace) / (b * sigmaStarSquaredTrace)
            identity = np.identity(b)
            return identity * float(b) * epsilon / sigmaStarTrace

    def getH1(self):
        """ generated source for method getH1 """
        return self.H1

    def getH0(self):
        """ generated source for method getH0 """
        return self.H0

    def isPositiveDefinite(self, m: np.matrix):
        """generated source for method isPositiveDefinite"""
        if m.shape[0] != m.shape[1]:
            raise Exception("Matrix must be non-null, square")
        eigenvalues = np.linalg.eigvals(m)
        test = [val > 0.0 for val in eigenvalues]
        return all(test)

    def forceSymmetric(self, m: np.matrix):
        """generated source for method forceSymmetric"""
        return np.tril(m) + np.triu(m.T, 1)


