
import sys
import math as math
import random as random
from itertools import product
from multiprocessing import Pool, Queue, cpu_count, Manager
import tensorflow as tf

from DataFrame import DataFrame
from MappingOperator import MappingOperator

# -------------------------------------------------------------
# File:
# -----
#   GeneticAlgorithm.py
# -------------------------------------------------------------
# Description:
# ------------
#   The GeneticAlgorithm.py file contains the Genetic Algorithm
#   class. The Genetic Algorithm class's responsibility is to
#   evolve the best mapping between Stimulus-Product pairs that
#   it can. It does this by evolving a set of solutions called
#   Mapping Operators by mimicking natural selection. The
#   algorithm can best be understood by following the function
#   calls in the run() function and reading each function's
#   documentation.
#
# Resources:
# ----------
#   https://en.wikipedia.org/wiki/Genetic_algorithm
#   https://blog.floydhub.com/introduction-to-genetic-algorithms/
#   https://www.toptal.com/algorithms/genetic-algorithms
#   http://www.cleveralgorithms.com/nature-inspired/evolution/genetic_algorithm.html
# -------------------------------------------------------------

class GeneticAlgorithm :

    # Evaluation Module
    evaluationModule = None
    
    # Population
    population = []
    populationSize = cpu_count() * 5
    
    # Fitnesses
    bestFitness = 99999999

    # Generations
    maxGenerations = 10000000

    # Algorithm
    selectionMethodIndicator = 0 # 0 = Roulette Wheel, 1 = Tournament
    rouletteWheelSelectionBias = .08
    tournamentPopulationProportion = .04    
    
    # Hyperparameters
    crossoverRate = .9
    mutationRate = .2
    mutationLikelihood = .1
    biasMutationLikelihood = .1
    topologicalMutationRate = .05
    valueReplacementBias = .2
    mutationMagnitudeLow = .00000000001
    mutationMagnitudeHigh = .01
    
    # Elitism
    elitismWeight = .3
    elites = []

    def __init__(self, evaluationModule) :

        # Set the evaluation module
        self.evaluationModule = evaluationModule

        # Set the parameters of the GA from the evaluation module
        self.populationSize = cpu_count() * evaluationModule.populationSizeFactor
        self.maxGenerations = evaluationModule.maxGenerations
        self.selectionMethodIndicator = evaluationModule.selectionMethodIndicator
        self.crossoverRate = evaluationModule.crossoverRate
        self.mutationRate = evaluationModule.mutationRate
        self.mutationLikelihood = evaluationModule.mutationLikelihood
        self.biasMutationLikelihood = evaluationModule.biasMutationLikelihood
        self.topologicalMutationRate = evaluationModule.topologicalMutationRate
        self.valueReplacementBias = evaluationModule.valueReplacementBias
        self.mutationMagnitudeLow = evaluationModule.mutationMagnitudeLow
        self.mutationMagnitudeHigh = evaluationModule.mutationMagnitudeHigh
        self.rouletteWheelSelectionBias = evaluationModule.rouletteWheelselectionBias
        self.tournamentPopulationProportion = evaluationModule.tournamentPopulationProportion
        self.elitismWeight = evaluationModule.elitismWeight
                
    def run(self) :

        # Generate the population
        self.generatePopulation()
        # Evaluate and sort it for the first time
        self.evaluatePopulation()
        self.sortPopulation()
        
        # Main GA algortihm loop
        generationCount = 0
        while generationCount < self.maxGenerations and self.population[-1].getFitness() > 0:

            # Run GA functions
            if self.selectionMethodIndicator == 0 :
                self.selectRouletteWheel()
            else :
                self.selectTournament()
            self.crossover()
            self.mutate()
            self.injectElites()
            self.evaluatePopulation()
            self.sortPopulation()
            self.saveElites()

            # Check fitnesses
            currentBestFitness = self.population[-1].getFitness()
            print("Generation ", generationCount, " : Fitness = ", currentBestFitness)
            if currentBestFitness < self.bestFitness :
                self.bestFitness = currentBestFitness
                print(" --------------------------------- New Best Fitness = ", self.bestFitness)
            
            generationCount = generationCount + 1

        # Set the best Mapping Operator on the Evaluation Module
        self.evaluationModule.setBestMappingOperator(self.population[-1])
        
    # Function:
    # --------- 
    #   generatePopulation()
    # --------------------------------------------------------------------------
    # Description:
    # ------------
    #   Generates the population of Mapping Operators for the Genetic Algorithm.
    # --------------------------------------------------------------------------
    # Parameters:
    # -----------
    #   None
    # --------------------------------------------------------------------------
    # Result:
    # --------
    #   The global population has been generated
    # --------------------------------------------------------------------------
    # Explanation:
    # ------------
    #   Delegates the generation of randomly initialized Mapping Operators to
    #   the Mapping Operator constructor. Each Mapping Operator needs to 
    #   know what size the vectors in the Product vector are in order to size 
    #   itself correctly. The Data Frame that is global to this class is the single
    #   source of truth for that value so we pass its value into the Mapping 
    #   Operators as we construct them. 
    # 
    #   Each Mapping Operator also needs to know how deep its backing tensor 
    #   should be. In the initial implementation this value is static and common
    #   to all Mapping Operators. In a future implementation this value may
    #   become owned by each Mapping Operator and altered through mutation
    #   and crossover. At this point the single source of truth for this common
    #   value is also stored in the Data Frame.
    # --------------------------------------------------------------------------
    def generatePopulation(self) :
        
        for i in range(self.populationSize) :
            self.population.append(MappingOperator(self.evaluationModule))

    # Function:
    # --------- 
    #   selectRouletteWheel()
    # --------------------------------------------------------------------------
    # Description:
    # ------------
    #   Selects members of the population to cross over.
    #
    #   Relies in the population being sorted by fitness value in DESCENDING order
    #   at this point
    # --------------------------------------------------------------------------
    # Parameters:
    # -----------
    #   None
    # --------------------------------------------------------------------------
    # Result:
    # --------
    #   A new population of selected members has been generated. The new population 
    #   is double the size of the original population. This new population will be
    #   made up of consecutive parents that are to be crossed over.
    #
    #   Ordering Schema:
    #   ----------------
    #   [Parent A1][Parent B1] , [Parent A2][Parent B2] , ... , [Parent AN][Parent BN]
    #
    #   Each pair of parents A and B for a given selection will be crossed over
    #   to form a new population that is of the original length indicated by the
    #   global variable populationSize. All of this is accomplished in the crossover
    #   function.
    #
    # --------------------------------------------------------------------------
    # Explanation:
    # ------------
    #   This implementation of the selection algorithm uses Roulette Wheel Selection.
    #   The goal of the algorithm is to select members in a manner that is
    #   proportionate to their fitness. In short, the fitter members get a larger
    #   piece of the probability pie; they have a higher likelihood of being
    #   selected.
    #
    #   This algorithm only works in the population at the beginning of it is
    #   sorted in DESCENDING order
    #
    #   More information about selection in general:
    #   --------------------------------------------
    #   Roulette Wheel selection is a preferred method in Genetic Algorithms because
    #   though the members with the best fitness have a greater chance of being 
    #   selected for crossover, the poorer members still have some chance which is
    #   important for retaining as much information in the population as possible as
    #   well as to effectively explore the search space.
    #
    #   Useful links:
    #   -------------
    #   A good explanation of various selection strategies:
    #       https://www.tutorialspoint.com/genetic_algorithms/genetic_algorithms_parent_selection.htm
    # --------------------------------------------------------------------------
    def selectRouletteWheel(self) :

        selectedPopulation = []

        # Load the fitness values from the population
        fitnessValues = []
        for mappingOperator in self.population :
            fitnessValues.append(mappingOperator.getFitness())

        # Sum the fitnesses of the population
        populationFitnessSum = 0
        for value in fitnessValues :
            populationFitnessSum = populationFitnessSum + value

        # Compute normalized fitness values
        for i in range(len(fitnessValues)) :
            fitnessValues[i] = fitnessValues[i] / populationFitnessSum

        # Compute cumulative normalized fitness values
        for i in reversed(range(len(fitnessValues) - 1)) :
            fitnessValues[i] = fitnessValues[i] + fitnessValues[i + 1]

        # Perform roulette wheel selection
        for i in reversed(range(len(self.population) * 2)) :
            randomFitness = random.uniform(0.0, self.rouletteWheelSelectionBias)

            k = len(fitnessValues) - 1
            while randomFitness > fitnessValues[k] :
                k = k - 1
            selectedPopulation.append(self.population[k])

        self.population = selectedPopulation

    # Function:
    # --------- 
    #   selectTournament()
    # --------------------------------------------------------------------------
    # Description:
    # ------------
    #   Selects members of the population to cross over.
    # --------------------------------------------------------------------------
    # Parameters:
    # -----------
    #   None
    # --------------------------------------------------------------------------
    # Result:
    # --------
    #   A new population of selected members has been generated. The new population 
    #   is double the size of the original population. This new population will be
    #   made up of consecutive parents that are to be crossed over.
    #
    #   Ordering Schema:
    #   ----------------
    #   [Parent A1][Parent B1] , [Parent A2][Parent B2] , ... , [Parent AN][Parent BN]
    #
    #   Each pair of parents A and B for a given selection will be crossed over
    #   to form a new population that is of the original length indicated by the
    #   global variable populationSize. All of this is accomplished in the crossover
    #   function.
    #
    # --------------------------------------------------------------------------
    # Explanation:
    # ------------
    #   This implementation of the selection algorithm uses Tournament Selection.
    #   In Tournament selection, members are selected by being pit against one
    #   another in a competition for a higher fitness. This is simple in practice:
    #   select N members at random and take the member with the highest fitness.
    #   The research says that picking two members will suffice instead of many.
    #   This increases variance in the fitness level.
    # --------------------------------------------------------------------------
    def selectTournament(self) :
        
        selectedPopulation = []

        for i in range(len(self.population) * 2) :

            selectedCompetitors = []
            for j in range(math.floor(len(self.population) * self.tournamentPopulationProportion)) :
                selectedCompetitors.append(self.population[random.randint(0, len(self.population) - 1)])

            championIndex = 0
            for j in range(len(selectedCompetitors)) :
                if selectedCompetitors[j].fitness < selectedCompetitors[championIndex].fitness :
                    championIndex = j

            selectedPopulation.append(selectedCompetitors[championIndex])
                
        self.population = selectedPopulation
    
    # Function:
    # --------- 
    #   crossover()
    # --------------------------------------------------------------------------
    # Description:
    # ------------
    #   Crosses over the Mapping Operators in the fitness-selected population
    # --------------------------------------------------------------------------
    # Parameters:
    # -----------
    #   None
    # --------------------------------------------------------------------------
    # Result:
    # --------
    #   A new resized population that has been crossed over from the selected
    #   parents in the population at the beginning of this function.
    #
    #   The result is that the genetic information from each parent 2-tuple
    #   has been assimilated into one single new child. The set of these
    #   children becomes the new population.
    # --------------------------------------------------------------------------
    # Explanation:
    # ------------
    #   This algorithm takes the ordered tuples of parents in the fitness-selected
    #   population  and crosses over their numerical features.
    #
    #   Crossover methodology:
    #   ----------------------
    #   This first iteration of the crossover algorithm only crosses over the
    #   values in the Mapping Operator Tensor by simply picking one of
    #   the two values in each parent to pass on to the single child. This
    #   random picking happens at a rate represented by the crossover rate
    #   that is global to the Genetic Algorithm.
    #
    #       Methodology example:
    #       --------------------
    #       Parent A Tensor: [1, 2, 3, 9]
    #       Parent B Tensor: [4, 5, 6, 8]
    #       Child Tensor:    [1, 5, 3, 8]
    #
    #   General Crossover information:
    #   ------------------------------
    #   Crossover occurs based on the specified crossover rate. Crossover rates are 
    #   meant to be high and usually always higher than mutation rates. Some 
    #   research-backed values are .8 - .99. Crossover is representative of the
    #   exploitative element of the algorithm. It seeks to capitalize on solutations
    #   that are already know to be good. It does this by recombinating the encodings
    #   of the population of solutions with each other. Solutions with a higher fitness
    #   have a commensurately better chance of passing on their information. This logic
    #   is carried out in the select routine. However, there is still a chance that a 
    #   better solution lies 'closer' to a current poor one. The GA takes this into 
    #   account by recombinating solutions with each other. This methodology allows
    #   these properties: a graceful approch to a better solution, consideration
    #   that a poorer solution may contain effective components, consideration that
    #   it is logical that better solutions working together will probably result in
    #   an even better solution, extreme explorations should be mitigated, and 
    #   exploration should be made on logical (good fitness) bases. Note that the 
    #   population size passed to this routine should be exactly double that of the
    #   working population because the generation of N childred requires N * 2 parents.     
    #
    # --------------------------------------------------------------------------
    def crossover(self) :
        
        crossedOverPopulation = []

        # Go through the double-sized population
        for i in range(int(len(self.population) / 2)) :

            # Extract the parents to be crossed over
            parentA = self.population[i]
            i = i + 1
            parentB = self.population[i]

            # Determine whether to crossover or not
            if random.uniform(0, 1) > self.crossoverRate :
                # If we dont then take the stronger parent
                if parentA.getFitness() <= parentB.getFitness() :
                    crossedOverPopulation.append(parentA)
                else :
                    crossedOverPopulation.append(parentB)
                continue

            newPopulationMemberBackingTensor = []

            # Get the backing tensors
            parentABackingTensor = parentA.getBackingTensor()
            parentABackingTensorBiases = parentA.getBackingTensorBiases()

            # Get the backing tensor biases
            parentBBackingTensor = parentB.getBackingTensor()
            parentBBackingTensorBiases = parentB.getBackingTensorBiases()

            # Set the primary parent to be the one with the shorter tensor
            if len(parentABackingTensor) > len(parentBBackingTensor) :
                # Set the backing tensors
                temp = parentABackingTensor
                parentABackingTensor = parentBBackingTensor
                parentBBackingTensor = temp

                # Set the backing tensor biases
                temp = parentABackingTensorBiases
                parentABackingTensorBiases = parentBBackingTensorBiases
                parentBBackingTensorBiases = temp
            
            # Crossover values in the backing tensor between the two parents
            for j in range(len(parentABackingTensor)) :

                newPopulationMemberBackingTensorRank2TensorMember = []
                parentABackingTensorRank2TensorMember = parentABackingTensor[j].numpy()
                parentBBackingTensorRank2TensorMember = parentBBackingTensor[j].numpy()

                for k in range(len(parentABackingTensorRank2TensorMember)) :

                    newPopulationMemberBackingTensorRank1TensorMember = []
                    parentABackingTensorRank1TensorMember = parentABackingTensorRank2TensorMember[k]
                    parentBBackingTensorRank1TensorMember = parentBBackingTensorRank2TensorMember[k]
                    
                    for l in range(len(parentABackingTensorRank1TensorMember)) :
                        
                        if random.uniform(0, 1) < .5 :
                            newPopulationMemberBackingTensorRank1TensorMember.append(parentBBackingTensorRank1TensorMember[l])
                        else :
                            newPopulationMemberBackingTensorRank1TensorMember.append(parentABackingTensorRank1TensorMember[l])

                    newPopulationMemberBackingTensorRank2TensorMember.append(newPopulationMemberBackingTensorRank1TensorMember)
                    
                newLayer = tf.convert_to_tensor(newPopulationMemberBackingTensorRank2TensorMember)
                newPopulationMemberBackingTensor.append(newLayer)    

            # Crossover the values in the backing tensor bias tensors
            newPopulationMemberBackingTensorBiases = []
            for j in range(len(parentABackingTensorBiases)) :

                if random.uniform(0, 1) < .5 :
                    newPopulationMemberBackingTensorBiases.append(parentBBackingTensorBiases[j])
                else :
                    newPopulationMemberBackingTensorBiases.append(parentABackingTensorBiases[j])
            
            newPopulationMember = MappingOperator(self.evaluationModule)
            newPopulationMember.setBackingTensor(newPopulationMemberBackingTensor)
            newPopulationMember.setBackingTensorBiases(newPopulationMemberBackingTensorBiases)

            crossedOverPopulation.append(newPopulationMember)

        self.population = crossedOverPopulation

    # Function:
    # --------- 
    #   mutate()
    # --------------------------------------------------------------------------
    # Description:
    # ------------
    #   Mutates the members of the population in the Genetic Algorithm.
    # --------------------------------------------------------------------------
    # Parameters:
    # -----------
    #   None
    # --------------------------------------------------------------------------
    # Result:
    # --------
    #   The global population has been mutated
    # --------------------------------------------------------------------------
    # Explanation:
    # ------------
    #   Mutates the numerical and shape features of the Mapping Operators in
    #   the population.
    #
    #   The current implementation of the mutation algortithm can:
    #   ----------------------------------------------------------
    #   1. Mutate the values in the Mapping Operator Tensor
    #
    #   An ideal future implementation of the mutation algorithm can:
    #   -------------------------------------------------------------
    #   1. Add a layer in the Z dimension of the rank 3 Tensor that is the
    #      Mapping Operator.
    #   2. Remove a layer in the Z dimension of the rank 3 Tensor that is the
    #      Mapping Operator.
    #   3. Mutate the values in the Mapping Operator Tensor
    #
    #       ** This ideal mutation strategy will affect how crossover is
    #          performed.
    #
    #   A more advanced form of mutation can:
    #   -------------------------------------
    #   1. Mutate mutation hyperparameters:
    #       1. tensorValueLow
    #       2. tensorValueHigh
    #       3. mutationMagnitude
    #       4. ratioBetweenValueReplacementAndValueAdjustment
    #
    #       ** This strategy would require a refactor to allow each Mapping
    #          Operator value to hold its own mutation hyperparameters
    #
    #   Numerical Mutation methodology:
    #   --------------------------------
    #   The Mutation of the values in the Tensor can be performed under several
    #   different strategies. However, in order to make things simple and to
    #   avoid excessive hyperparameter tuning I will use a balanced strategy.
    #
    #       A value can be:
    #       ---------------
    #       1. Replaced: The value is completely thrown out and replaced with a
    #                    completely within the range of possible tensor values 
    #       2. Adjusted: The value is altered with tiny numerical adjustments
    #       
    #       The fact of the matter is that I don't quite know which is objectively
    #       better. There will be an element of experimentation. However, the real
    #       power of the Genetic Algorithm in this incarnation is that it has the
    #       ability to implicity select the best strategy. I am choosing to trust
    #       the algorithm and allow it to use both strategies at its discretion.
    #       
    #       One line of thought to pursue is that the choice of mutation strategy
    #       is likely affected by the evaluation function strategy. Obviously we
    #       are targeting a zero error mapping between the Stimuli and Product
    #       vectors. However, because the values in the Product vectors are 
    #       integers and not floating point values there are concerns that while
    #       the algorithm will converge smoothly, it may never converge exactly.
    #       Numerically speaking, it is beneficial to have a smooth and
    #       continuous optimization curve instead of discretely disjoint values
    #       where things like primes might cause problems in convergence. One
    #       strategy to get the best of both worlds is to apply a flooring
    #       function to the output of the Mapping Operator Tensor before it
    #       is evaluated. Then integers are evaluated against integers while
    #       allowing the Mapping Operator Tensor to be continuously valued.
    # 
    #   More information about Mutation in general:
    #   -------------------------------------------
    #   Mutation occurs based opon the specified mutation rate. It serves to 
    #   explore the search space in hopes that a more distant solution may be
    #   better. In this implementation mutation happens on an element-wise basis.
    #   Mutation rates are generally always smaller than crossover rates and are
    #   usually very, very small. Some researched-backed values are .01 to .1 .
    # --------------------------------------------------------------------------
    def mutate(self) :
        
        for mappingOperator in self.population :
            mappingOperator.mutate(self.mutationRate,
                                   self.mutationLikelihood,
                                   self.biasMutationLikelihood,
                                   self.mutationMagnitudeLow,
                                   self.mutationMagnitudeHigh,
                                   self.topologicalMutationRate,
                                   self.valueReplacementBias)
    # Function:
    # --------- 
    #   evaluatePopulation()
    # --------------------------------------------------------------------------
    # Description:
    # ------------
    #   Uses the Data Frame to run and measure the fitness of each Mapping
    #   Operator in the population.
    # --------------------------------------------------------------------------
    # Parameters:
    # -----------
    #   None
    # --------------------------------------------------------------------------
    # Result:
    # --------
    #   The global population has had each of their fitnesses evaluated
    # --------------------------------------------------------------------------
    # Explanation:
    # ------------
    #   We relegate the logic for running and evaluating a given Mapping
    #   Operator to the Data Frame so just pass each Mapping Operator into
    #   the Data Frame's evalutation function. The evaluateMappingOperator()
    #   function in the Data Frame sets the measured fitness value on the 
    #   Mapping Operator that is passed into it.
    #
    #   This implementation uses Python's multiprocessing library to evaluate
    #   the members of the population on all available processors.
    # --------------------------------------------------------------------------
    def evaluatePopulation(self) :

        # Define the population accumulator
        multiprocessingManager = Manager()
        populationAccumulator = multiprocessingManager.Queue()
       
        # Danger check
        if len(self.population) % cpu_count() != 0 :
            print("The population is not divisible by the CPU count!")
            print("The CPU count is: ", cpu_count())
            print("Exiting...")
            sys.exit()

        # Split the population into equal parts in accordance with the cpu count
        splitLength = cpu_count()
        splitPopulation = [self.population[i * splitLength:(i + 1) * splitLength] for i in range((len(self.population) + splitLength - 1) // splitLength)]
            
        # Initialize the process pool
        with Pool(processes = cpu_count()) as processPool :

            # Map the population to a process in the pool and execute it
            for subPopulation in splitPopulation :
                processPool.apply(self.evaluateSubPopulation, (subPopulation, populationAccumulator))

        # Set the accumulated evaluated population back to the global population
        accumulatedPopulation = []
        while populationAccumulator.empty() != True :
            accumulatedPopulation.append(populationAccumulator.get())
        
        self.population = accumulatedPopulation

    # Function:
    # --------- 
    #   evaluateSubPopulation()
    # --------------------------------------------------------------------------
    # Description:
    # ------------
    #   Evaluates the sub popuation passed to it and places it in the accumulator
    #   queue.
    # --------------------------------------------------------------------------
    # Parameters:
    # -----------
    #   subPopulation - The portion of the population to evaluate in this Process.
    #   accumulator - A Python multiprocessing.Queue() object that acts as an
    #                 accumulator for the evaluated Mapping Operators
    # --------------------------------------------------------------------------
    # Result:
    # --------
    #   The evaluated members of the sub population have been placed in the
    #   accumulator queue.
    # --------------------------------------------------------------------------
    # Explanation:
    # ------------
    #   This function evaluates the members of a portion of the global population.
    #   It is set off as a Process in Python's multiprocessing library.
    # --------------------------------------------------------------------------
    def evaluateSubPopulation(self, subPopulation, accumulator) :
        
        for mappingOperator in subPopulation :
            self.evaluationModule.getDataFrame().evaluateMappingOperator(mappingOperator)
            accumulator.put(mappingOperator)
            
    # Function:
    # --------- 
    #   saveElites()
    # --------------------------------------------------------------------------
    # Description:
    # ------------
    #   Saves the elites of a run to be injected in the next generation.
    # --------------------------------------------------------------------------
    # Parameters:
    # -----------
    #   None
    # --------------------------------------------------------------------------
    # Result:
    # --------
    #   The global population of elites has been loaded with the best members
    #   of the previous generation. The number of elites saved is controlled
    #   by the global parameter elitismWeight.
    # --------------------------------------------------------------------------
    # Explanation:
    # ------------
    #   Elitism boosts the convergence of the algorithm by continually injecting
    #   the best genetic material into the population at every generation. We
    #   save the best few members of the population in this function to be
    #   injected in the next generation.
    # --------------------------------------------------------------------------
    def saveElites(self) :

        self.elites.clear()

        numberToSave = int(self.elitismWeight * self.populationSize)

        startSavingPoint = len(self.population) - numberToSave
        for i in range(startSavingPoint, len(self.population)) :
            self.elites.append(self.population[i].clone())

    # Function:
    # --------- 
    #   injectElites()
    # --------------------------------------------------------------------------
    # Description:
    # ------------
    #   Injects the elites from the last generation into the current population.
    # --------------------------------------------------------------------------
    # Parameters:
    # -----------
    #   None
    # --------------------------------------------------------------------------
    # Result:
    # --------
    #   The global population has been injected with the elites from the last
    #   generation.
    # --------------------------------------------------------------------------
    # Explanation:
    # ------------
    #   Elitism boosts the convergence of the algorithm by continually injecting
    #   the best genetic material into the population at every generation. We
    #   inject the elites into the global population in this function
    # --------------------------------------------------------------------------
    def injectElites(self) :

        for i in range(len(self.elites)) :
            self.population[i] = self.elites[i]

    # Function:
    # --------- 
    #   sortPopulation()
    # ---------------------------------------------------------------------------
    # Description:
    # ------------
    #   Sorts the Mapping Operators in the population by their fitness level
    #   in DESCENDING order.
    # ---------------------------------------------------------------------------
    # Parameters:
    # -----------
    #   None
    # ---------------------------------------------------------------------------
    # Result: 
    # --------
    #   The population has been sorted by fitness in DESCENDING order.
    # ---------------------------------------------------------------------------
    # Explanation:
    # ------------
    #   Uses Merge Sort to sort the evaluated population to get set up for
    #   the Selection process in the next iteration of the algorithm.
    # ---------------------------------------------------------------------------
    def sortPopulation(self) :
        self.population = self.mergeSort(self.population)

    # Function:
    # --------- 
    #   replacePopulationWithBestMember()
    # --------------------------------------------------------------------------
    # Description:
    # ------------
    #   Wipes out the current population and replaces it with a population
    #   constituted of just the best member from the previous generation.
    # --------------------------------------------------------------------------
    # Parameters:
    # -----------
    #   The best member from the previous generation.
    # --------------------------------------------------------------------------
    # Result:
    # --------
    #   The global population has been replaced by one comprised of only the
    #   best member from the last generation.
    # --------------------------------------------------------------------------
    # Explanation:
    # ------------
    #   In order to accelerate convergence we can replace the population with
    #   the fittest member when a new best fitness is found or when a new
    #   generation fails to produce a new best fitness.
    # --------------------------------------------------------------------------
    def replacePopulationWithBestMember(self, bestMember) :
        self.population.clear()
        for i in range(self.populationSize) :
            self.population.append(bestMember.clone())
        
    # Function:
    # --------- 
    #   mergeSort()
    # ---------------------------------------------------------------------------
    # Description:
    # ------------
    #   The sorting portion of the Merge Sort algorithm.
    # ---------------------------------------------------------------------------
    # Parameters:
    # -----------
    #   mergingPopulation - The population as it stands after the Evaluation process.
    # ---------------------------------------------------------------------------
    # Returns: 
    # --------
    #   Portions of the population based on the recursive depth. The shallowest
    #   depth returns the fully sorted population.
    # ---------------------------------------------------------------------------
    # Explanation:
    # ------------
    #   Performs the sorting portion of Merge Sort. Merge Sort is used as the
    #   sorting algorithm to order the Mapping Operators in the population
    #   by fitness value.
    #
    #   Merging is done in DESCENDING ORDER
    # ---------------------------------------------------------------------------
    def mergeSort(self, mergingPopulation) :

        if len(mergingPopulation) == 1 :
            return mergingPopulation

        mid = len(mergingPopulation) // 2
        a = mergingPopulation[:mid]
        b = mergingPopulation[mid:]

        sortedA = self.mergeSort(a)
        sortedB = self.mergeSort(b)

        return self.merge(sortedA, sortedB)

    # Function:
    # --------- 
    #   merge()
    # ---------------------------------------------------------------------------
    # Description:
    # ------------
    #   The merging portion of the Merge Sort algorithm.
    # ---------------------------------------------------------------------------
    # Parameters:
    # -----------
    #   a - The first half of the population to be merged
    #   b - The second half of the population to be merged
    # ---------------------------------------------------------------------------
    # Returns: 
    # --------
    #   The merged population halves in sorted order.
    # ---------------------------------------------------------------------------
    # Explanation:
    # ------------
    #   Performs the merging portion of Merge Sort. Merge Sort is used as the
    #   sorting algorithm to order the Mapping Operators in the population
    #   by fitness value. This is one of two functions used in the algorithm.
    #
    #   Merges in DESCENDING ORDER!
    # ---------------------------------------------------------------------------
    def merge(self, a, b) :

        merged = []

        while len(a) > 0 and len(b) > 0 :

            if a[0].getFitness() > b[0].getFitness() :
                merged.append(a.pop(0))
            else :
                merged.append(b.pop(0))

        while len(a) > 0 :
            merged.append(a.pop(0))

        while len(b) > 0 :
            merged.append(b.pop(0))

        return merged